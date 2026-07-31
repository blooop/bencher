# Plan 22 — Grammar Phase 1: Self-Describing Canonical Dataset

**Goal:** Make every cell of the result dataset meaningful in any process — no
run-local indices — so any slice of a result can be rendered after any pickle
round-trip. This is phase 1 of 5 of the A6 migration
([A6 — Grammar of ND data](architecture/A6-grammar-of-nd-data.md), Law 1 and Law 10);
it is a pure data-layer change with **one** intended visual improvement (D4) and no
other rendering changes.

**Branch name:** `feat/grammar-data-model`

**⚠️ Read first:** A6 §2 Law 1 and Law 9 (the defensive posture for old pickles), and
the cache-safety section below. Results cached before this change must keep
rendering — the same `getattr`-for-old-pickles discipline as PR #994. Do not touch
selection, channels, or the planner; those are phase 2 (a future plan).

---

## Problem statement (with evidence)

### P1 — `ResultDataSet` cells are run-local integers

A worker returning `ResultDataSet(obj)` is stored as an **index into
`bench_res.dataset_list`** (`bencher/result_collector.py:411-414`), with the payload
kept in the list. The cell value is only meaningful while paired with the exact
`dataset_list` that produced it.

Consequence, already worked around in the pane recursion
(`bencher/results/bench_result_base.py:913-919`): when an `over_time` history is
loaded, historical cells index a *previous* run's list, so rendering is forcibly
restricted to `dataset.isel(over_time=-1)` — **dataset history exists in the data but
cannot be rendered**. The comment at `:913` documents this as a known limitation.

### P2 — The blob family already solved this, and collection already materializes

`ResultImage`, `ResultVideo`, `ResultPath`, `ResultRerun` cells store **file paths**
into `cachedir` — self-describing in any process that shares the cache filesystem, and
they survive the collect/render split (`bencher/render.py:44-70` strips only
`object_index`; path cells pass through untouched).

The materialize-at-collect precedent exists too:
`_materialize_result_value` (`bencher/result_collector.py:147`) already reduces a
`ComposableContainerRerun` to a single `.rrd` path during collection (PR #1007), before
caching. `ResultDataSet` is the one payload-bearing type that skipped this pattern.

### P3 — Three missing-value dialects, checked ad hoc

Numeric kinds use NaN; path/string kinds use the string `"NAN"`; index-backed kinds use
`-1`. The single oracle exists — `result_missing_fill` / `result_is_missing`
(`bencher/variables/results.py:636,646`) — but call sites still hand-roll checks
(e.g. `_over_time_filepath` and the index guards in `ds_to_container`,
`bench_result_base.py:1104-1160`). Any new consumer (the phase-2 planner) would have to
learn all three dialects.

### P4 — `ResultHmap` is a parallel data universe

`ResultHmap` (`bencher/variables/results.py:254`) stores **nothing in the dataset**;
its data lives out-of-band in `bench_res.hmaps`
(`bencher/result_collector.py:433-434`). It is also the only pathway with
alphabetically-sorted dims (`bench_cfg.hmap_kdims = sorted(dims_name)`,
`bencher/bencher.py:1094`) versus declaration order everywhere else (A6 audit
finding #14). It structurally cannot join a canonical-dataset architecture, and its use
case (a holoviews object per sample) is covered by `ResultContainer` /
`ResultReference` with a declared container (PR #994).

---

## Proposed design

### D1 — A content-addressed blob store helper

New module `bencher/blob_store.py`:

```python
def materialize_blob(obj, cache_dir: Path) -> str:
    """Serialize obj under cache_dir/blobs/, named by content hash; return the path."""
```

- `pd.DataFrame` → parquet; `xr.Dataset` / `xr.DataArray` → netCDF; `bytes` → raw
  file; an existing path-like → returned unchanged.
- Anything else picklable → `.pkl` blob. `ResultDataSet` documents its payload as "any
  picklable object" (`bencher/variables/results.py:486-509`), so a fallback is required
  for compatibility. Flag it in the docstring as the pickle surface A3 wants gone, so
  the A3 migration knows where to look. **OWNER DECISION (recorded, default = allow):**
  keep the pickle fallback, or restrict payloads to DataFrame/xarray and break the
  documented contract now. Recommendation: allow — A3 is the right place to tighten
  this, with its own deprecation story.
- Filename = `sha256(serialized bytes)[:16]` + extension. Content addressing
  deduplicates identical payloads across repeats and time points for free.
- Loading counterpart `load_blob(path)` dispatches on extension.

### D2 — `ResultDataSet` cells become paths, materialized at collect

In `store_results` (`bencher/result_collector.py:410-414`), the `ResultDataSet` branch
calls `materialize_blob(result_value.obj if isinstance(...) else result_value, ...)`
and stores the **path string** in the cell — exactly parallel to the
`ComposableContainerRerun` handling three lines up.

- The missing sentinel for `ResultDataSet` changes from `-1` to the blob-family
  sentinel (`"NAN"`), making `result_missing_fill` uniform across every
  non-`ResultReference` blob kind.
- `dataset_list` (`bench_result_base.py:105`) stays, as the **legacy read path only**
  (D3). New runs no longer append to it.
- Worker-facing API is unchanged: `self.out_ds = bn.ResultDataSet(df)` and the whole
  declared-container precedence chain from PR #989 behave identically.

### D3 — Render path reads both generations

`ds_to_container`'s `ResultDataSet` branch (`bench_result_base.py:1130-1140`) becomes:

1. cell is a `str` path → `load_blob(path)`, then the existing container precedence
   (renderer-supplied → sample's → class's → raw object);
2. cell is an `int` (a result pickled or cached before this plan) → the current
   `dataset_list[val]` lookup, guarded with `getattr(self, "dataset_list", None)`;
   missing list → a labelled placeholder pane plus a log line, never a crash (Law 9
   posture);
3. missing sentinel (either generation's: `-1` or `"NAN"`) → existing missing
   handling via the oracle (D5).

### D4 — Delete the `isel(over_time=-1)` restriction

With path cells, historical `ResultDataSet` entries are loadable, so the special case
at `bench_result_base.py:913-919` is removed and dataset results participate in
`over_time` rendering like every other blob type. **This is the one intended visual
change** of this plan: `over_time` reports gain the previously-hidden history points
for dataset results. Per A6 Law 10, the PR includes regenerated gallery docs so the
before/after is reviewable. Legacy int cells inside a mixed history render via D3(2)
where the list is available and the D3 placeholder where it is not — which is exactly
the honest representation of what an old cache can support.

### D5 — One missing-value oracle

Sweep every hand-rolled missing check in `bench_result_base.py` (and the history/aging
paths that import the helpers) to call `result_is_missing`. Stored fill values do
**not** change for existing types (NaN / `"NAN"`), so previously cached datasets and
`over_time` histories remain byte-compatible; only `ResultDataSet`'s fill moves
(D2), and `result_is_missing` accepts both its generations (`-1` and `"NAN"`) for the
type, permanently — mixed-generation history concat produces object cells of both
kinds and must keep rendering.

### D6 — Deprecate `ResultHmap`

Emit `DeprecationWarning` when a `ResultHmap` is declared, pointing at
`ResultContainer`/`ResultReference` with a declared container. Documentation note in
`docs/how_to_use_bencher.md`. **No behavioral change in this plan**; removal (including
`hmaps`, `result_hmaps`, `hmap_kdims`, and the `to_nd_layout`/`to_holomap` consumers)
is scheduled with phase 3, when the panel backend is rewritten anyway.

### D7 — `ResultReference` is explicitly out of scope

It remains the documented same-process escape hatch (A6 Law 1): live object, stripped
by both `cache_results` (`result_collector.py:454-460`) and `save_result`
(`render.py:60-68`), never load-bearing for the core algebra. Its docstring gains that
exact sentence.

---

## Cache safety

- `hash_persistent()` is untouched: no `__slots__` additions, and `_hash_slots` hashes
  slot *values* on the parameter class, not cell contents. Assert with a
  `TestPersistentHashUnaffected`-style test (the PR #989/#994 pattern).
- Sample-cache **keys** derive from inputs and are unaffected. Sample-cache **values**
  produced before this plan contain int cells plus a pickled `dataset_list`; D3(2)
  keeps them rendering. No cache-version bump required. **OWNER DECISION (recorded,
  default = no bump):** if review disagrees, bumping `CACHE_VERSION` to 6 is the
  conservative alternative at the cost of invalidating warm caches.
- `over_time` history files written before this plan contain `-1` sentinels and int
  indices; D5's dual-generation oracle plus D3 cover them. New history entries written
  after this plan are fully renderable (D4) — that is the payoff.
- Blob files live under `cachedir/blobs/`, alongside the existing `cachedir/rrd/`
  convention; the render process already requires a shared cache filesystem
  (A6 §"render.py constraints"). Orphan cleanup is A4's artifact-manifest scope, not
  this plan's.

## Tests

`test/test_grammar_data_model.py` (new), plus additions where noted:

1. `materialize_blob` round-trips DataFrame (parquet), `xr.Dataset` (netCDF), bytes,
   and an arbitrary dataclass (pickle); identical payloads produce identical paths
   (content addressing); `load_blob` dispatches by extension.
2. A sweep with a `ResultDataSet` var stores `str` cells, appends nothing to
   `dataset_list`, and renders through the declared-container chain identically to
   before (extend `test/test_dataset_result.py` golden behaviors).
3. Collect → `save_result` → fresh-process `load_result` → render succeeds for
   `ResultDataSet` (extend the split-render layer; run under
   `BENCHER_FORCE_SPLIT_RENDER=1`).
4. A hand-built legacy result (int cells + `dataset_list`) still renders; the same
   result with `dataset_list` deleted renders the D3 placeholder without raising.
5. `over_time` with `ResultDataSet` across ≥2 time points renders **all** points
   (the D4 payoff), including a mixed history of one legacy int cell and one path cell.
6. Hash invariance: `hash_persistent()` for every `Result*` class is byte-identical to
   values recorded before the change.
7. `result_is_missing` truth table: NaN/`"NAN"`/`-1`/valid path/valid int, per type.
8. Declaring a `ResultHmap` warns `DeprecationWarning`; existing hmap tests still pass
   with the warning filtered.

## Validation

- `pixi run ci` clean; full suite green.
- `pixi run test-split` (the `BENCHER_FORCE_SPLIT_RENDER=1` job) green.
- `pixi run generate-docs`, and attach the regenerated gallery diff to the PR for owner
  before/after review (A6 Law 10) — expected diffs: dataset-result `over_time`
  examples only.

## Not in this plan

- The `Plan` type, channels, planner, capability tables (phase 2).
- Any renderer rewrite (`_to_panes_da` etc., phase 3) beyond deleting the D4 special
  case.
- Changing stored fill values for existing types, `ResultReference` semantics, or
  removing `dataset_list`/`ResultHmap` code (phase 3).
- A2/A3-style serialization of plot *choices* — plans/views arrive in phases 2 and 5.

## Amendments discovered during implementation

Recorded per the plans-README rule that claims which stopped holding are stated
rather than silently worked around:

1. **The environment is netCDF3-only** (scipy is the sole xarray engine), which
   silently narrows int64→int32 and raises on other values. D1 therefore carries an
   empirically-derived dtype whitelist (`_NETCDF3_SAFE_DTYPES` in
   `bencher/blob_store.py`, evidence in its comment); Datasets/DataArrays with unsafe
   dtypes take the pickle fallback rather than risk corruption. Structured-format
   failures of any kind fall back to pickle with a logged warning — a worker payload
   inside the documented contract must never abort a sweep.
2. **D4's legacy wording was wrong and is amended.** "Render via D3(2) where the list
   is available" would resolve in-range historical indices against the *final* run's
   `dataset_list`, rendering the current payload under historical labels (reproduced
   in review). Legacy int cells are trusted only at the final time event; earlier
   events render the placeholder.
3. **No path passthrough in the blob store**: a str/Path payload is pickled like any
   object so the render-time container receives exactly what the worker stored.
4. **Per-sample containers** are preserved by materializing the pickled
   `ResultDataSet` wrapper (such payloads store as `.pkl`); an unpicklable per-sample
   container (e.g. a lambda) is dropped with a warning and the bare payload stored —
   class-level containers still apply.
5. Both owner decisions resolved to their recorded defaults: the pickle fallback is
   allowed (flagged for A3), and no `CACHE_VERSION` bump.
6. D4's gallery evidence required a new example —
   `example_result_dataset_1d_over_time` — since no existing example combined
   `ResultDataSet` with `over_time`.

## Coordination

- **A3/A4:** D1's store is a deliberate step toward A4's artifact manifests — keep the
  formats (parquet/netCDF) and the `cachedir` layout consistent with A3's
  netCDF-plus-manifest direction; the pickle fallback is the flagged exception.
- **A6:** this plan is Law 1 and the first PR of the Law 10 stack. Phase 2's plan doc
  should be written only after this lands, against the post-phase-1 codebase.
- **Plan 12 (portable artifact paths):** blob paths should be stored relative to
  `cachedir` if plan 12 has landed by implementation time; otherwise absolute, with a
  note for plan 12 to sweep.
