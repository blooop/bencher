# Plan 09 — Result Cache & History Invalidation Correctness

**Status: IMPLEMENTED** (v1.114.0, together with plan 14 — see
`plans/14-history-schema-reconciliation.md` for the design record). D1 and D2
landed as described (§4's sorted-tuple combiner, names in every per-var
identity); D3's index + `on_history_reset` landed with plan 14's per-column
events routed through the same policy. Kept for the analysis; line numbers
reference the pre-fix source.

**Goal:** Fix three correctness defects in how the benchmark-config hash
(`BenchCfg.hash_persistent`) invalidates the result cache (Layer B) and the
`over_time` history cache (Layer C):

1. It is **sensitive to list order** — for `result_vars` *and* `const_vars` — so
   reordering the result columns, or reordering a dict of constants, silently
   discards a benchmark's entire accumulated history and regression baselines,
   though nothing about *what* is measured changed.
2. The per-variable hash **excludes the variable name** — for result vars *and*
   input/sweep vars — so *renaming* a variable does not change the key, yet the
   stored history is keyed internally by name: silent, partial history
   corruption (a different flavor per variable kind — see D2).
3. Invalidation is **silent**: when the key moves, history vanishes with only an
   info-level log. D3 proposes a last-seen-key index and an `on_history_reset`
   policy knob to make resets observable.

These semantics demonstrably violate user expectations: large downstream
benchmark suites document the key in their own contributor docs as "a hash of
the *set* of input/result/const vars" (it is not — it is an ordered fold), and
invent conventions such as routing every result-var list through one shared
constant purely to protect against resets they cannot see. When users build
folklore defenses around a cache key, the key should change, not the users.

**⚠️ Read first:** This plan deliberately revisits `hash_persistent()` *semantics*,
which `plans/architecture/A4-caching-architecture.md` §5 says NOT to change. A4's
"don't touch it" refers to the intentional exclusion of display-only fields (e.g.
`title`) — that guidance stands; the ordering/naming behavior here is a genuine
defect, not an intentional exclusion. Coordinate with A4: if A4 Phase C2 (the
`bencher/caching/keys.py` key module) has landed, implement this fix there
instead of in `bench_cfg.py`. Note also that A4's §2 W5 row says "Layer C key
excludes repeats" — stale against current source (see §1); do not inherit it.

**Rules:**
- Always use the pixi environment (`pixi run ...`, e.g. `pixi run pytest`). Never
  run tools directly.
- Work on a feature branch, never `main` (merging to `main` with a version bump
  auto-publishes to PyPI — see plans/01).
- The `hash_persistent()` determinism contract (the auto-discovering determinism
  tests) must still hold: identical configs → identical hash across processes.
- Any change to a cache key is cache-busting. Bump `CACHE_VERSION`
  (`bencher/cache_management.py:38`) in the same PR and add a headline CHANGELOG
  entry; do not migrate pickled legacy entries — a one-time miss is the accepted
  recovery path.
- If a step fails in a way this plan does not cover, stop and report rather than
  improvising.

---

## 1. Background — where the key is used

`BenchCfg.hash_persistent(include_repeats)` (`bencher/bench_cfg.py:757`) is the
persistent identity of a benchmark run. Both on-disk caches key on the **same**
hash, computed once as `bench_cfg.hash_persistent(True)` (`bencher/bencher.py:678`):

- **Layer B — result cache** (`cachedir/benchmark_inputs`): lookup at
  `bencher.py:701-703`, write via `cache_results` (`result_collector.py:391`).
- **Layer C — `over_time` history** (`cachedir/history`): the same hash is passed
  to `load_history_cache` (`bencher.py:725-731`; `result_collector.py:399`), which
  loads `ds_old = c[bench_cfg_hash]` and does `xr.concat([ds_old, dataset],
  "over_time")` (`result_collector.py:465`, xarray's default `join="outer"`).
  A missing key means "no history" → fresh series.

(The `include_repeats=False` variant at `bencher.py:682` is vestigial: it is
threaded into `WorkerJob.bench_cfg_sample_hash` but never read — the sample
cache keys on concrete function inputs + tag only (`worker_job.py`). Repeats
are intentionally in the history key so historical arrays have the same
shape — see the comment at `bench_cfg.py:773-775`.)

Crucially, identity *inside* the stored dataset is by **name**: data variables
are created under each result var's `.name` (`result_collector.py:229`), and
dims/coords are named by each input var's `.name` in `input_vars` list order
(`DimsCfg`, `bench_cfg.py:1075`). Identity *in the cache key* is type/units/shape
— never the name (see §2). That disagreement is the root of defect D2.

## 2. The defects

### D1 — `result_vars` and `const_vars` order changes the key (it should be a no-op)

`hash_persistent` folds each variable into a running accumulator **in list order**
(`bench_cfg.py:796-801`):

```python
all_vars = (self.input_vars or []) + (self.result_vars or [])
for v in all_vars:
    hash_val = hash_sha1((hash_val, v.hash_persistent()))

for v in self.const_vars or []:
    hash_val = hash_sha1((hash_val, v[0].hash_persistent(), hash_sha1(v[1])))
```

The fold is a non-commutative chained hash: permuting `result_vars` changes the
final hash whenever the permuted vars have distinct `hash_persistent()` values —
distinct class or units (`direction` is deliberately excluded via `_hash_exclude`,
`bencher/variables/results.py:107`). The *set* of measured quantities is
unchanged, yet both layers miss and the entire history is silently dropped.

The same applies to `const_vars`, where order is even less meaningful: a
user-supplied dict becomes `list(dict.items())` (`bencher.py:436-437`), and when
`const_vars` is omitted it is auto-derived from `get_input_defaults()` in class
*declaration* order (`bencher.py:376`, `variables/parametrised_sweep.py:126-138`).
Reordering a kwargs dict or the param declarations in a sweep class resets
history, yet const order affects nothing but the title string (`bencher.py:448-452`).
The const *value* being folded (`hash_sha1(v[1])`) is intentional and correct —
a different constant is a different experiment — only the *order* sensitivity is
the defect.

The intuitive mental model is that result vars and constants form a *set* whose
order is a presentation detail. Nothing documents reordering as a full
invalidation event, and the determinism tests only assert *same input → same
hash*, never *reordered-but-equivalent input → same hash*.

**Reproduction** (add as a failing test, then make it pass):

```python
import bencher as bn
from bencher.bench_cfg import BenchCfg

def key(result_vars, const_vars=()):
    c = BenchCfg(bench_name="demo", tag="demo", over_time=True, input_vars=[],
                 result_vars=list(result_vars), const_vars=list(const_vars))
    return c.hash_persistent(include_repeats=False)

a = bn.ResultBool(units="ratio")
b = bn.ResultFloat(units="s")
w = bn.FloatSweep(units="m", bounds=[0, 1]);    w.name = "width"
g = bn.FloatSweep(units="deg", bounds=[0, 90]); g.name = "angle"

assert key([a, b]) == key([b, a])  # FAILS: result reorder resets history
assert key([a], [(w, 0.5), (g, 30.0)]) == key([a], [(g, 30.0), (w, 0.5)])  # FAILS: const reorder
```

### D2 — the per-variable hash ignores the variable name (result *and* input vars)

- **Result vars**: `_hash_slots` (`bencher/variables/results.py:50`) hashes the
  concrete class name plus every non-excluded `__slots__` entry, stopping the
  MRO walk at the param framework — so the Parameter's `name` is never hashed.
  With `direction`/`share_axis`/`max_time_events` excluded (`results.py:102-107`),
  a `ResultFloat`'s identity is effectively *(class, units)*.
- **Input/sweep vars**: `SweepBase._sweep_identity` (`bencher/variables/sweep_base.py:111-130`)
  returns `(type(self).__name__, self.units, self.samples)` plus subclass
  extensions — `objects` (`variables/inputs.py:64`), bounds + `sample_values`
  (`inputs.py:538-541`), `step` (`inputs.py:628-631`) — and never `self.name`.

Consequences (each verified against xarray 2025.6.1; re-verify in the pixi env):

- **Renaming a result var → dead-column split.** Layer C still finds `ds_old`,
  but it holds a data variable under the *old* name while the fresh run produces
  the *new* name. The outer-join concat yields both columns: the renamed metric
  holds only the latest point (looks reset), while the old-named column persists
  as a dead column that never receives new data — and its NaN fill is
  indistinguishable from genuinely missing samples (`result_collector.py:228`).
- **Renaming an input var → phantom-dimension broadcast.** The key is unchanged
  but the history's *dimension* name differs from the fresh dataset's. Here
  `xr.concat` does **not** NaN-split — it broadcasts: the combined dataset gains
  *both* dims, every data variable is duplicated across the phantom dimension,
  and there are **zero NaNs** to betray it — history silently gains points at
  coordinate combinations never measured, and regression statistics then
  aggregate the duplicates. Verify with:

  ```python
  import numpy as np, xarray as xr
  old = xr.Dataset({"m": (("speed", "over_time"), np.ones((2, 3)))},
                   coords={"speed": [0.1, 0.2], "over_time": [0, 1, 2]})
  new = xr.Dataset({"m": (("velocity", "over_time"), 2 * np.ones((2, 1)))},
                   coords={"velocity": [0.1, 0.2], "over_time": [3]})
  out = xr.concat([old, new], "over_time")   # dims: speed × velocity × over_time
  assert not np.isnan(out["m"]).any()        # fabricated points, no NaN tell
  ```

- **Const identity collisions.** Consts are input-type params, so holding
  `width=0.5` vs `depth=0.5` constant (same class/units/bounds) yields the *same*
  key — Layer B can serve cached results for a different experiment.
- Conversely, this is *why* D1's fix is safe for same-type vars: they are already
  indistinguishable to the key, so only reorders of distinct-identity vars move it.

**Reproduction** (names set directly to isolate the hash behavior; they are
normally bound via class-attribute declaration):

```python
import bencher as bn

x = bn.ResultFloat(units="s"); x.name = "duration"
y = bn.ResultFloat(units="s"); y.name = "latency"
p = bn.FloatSweep(units="m", bounds=[0, 1]); p.name = "speed"
q = bn.FloatSweep(units="m", bounds=[0, 1]); q.name = "velocity"
assert x.hash_persistent() != y.hash_persistent()  # FAILS: result rename invisible
assert p.hash_persistent() != q.hash_persistent()  # FAILS: input rename invisible
```

### D3 — invalidation is silent

When the key changes (D1) or the concat mismatches (D2), history vanishes or
corrupts with only info-level logs (`result_collector.py:431,435`) — a user
cannot distinguish an intended reset from an accidental one. (A4 §3.5 / W5
already argue for *reporting* history incompatibilities; D2 is a concrete case.)

**Concrete remediation:** maintain a small per-`(bench_name, tag)` index in the
history cache holding the last-seen `hash_persistent` key plus a compact identity
summary — ordered `(kind, name, class, units)` tuples for input/result/const
vars. (Prior art: Layer B stores a `bench_name`-keyed hash list alongside its
hash-keyed entries, `result_collector.py:396-397`.) On a key mismatch where
prior history exists, surface it — once per benchmark, at history-load time —
through **all three** of these, so it is visible whether the user watches a
console, a CI log, or only the rendered report:

1. **A `logging.WARNING`** (module logger, not the current `INFO`/`DEBUG` at
   `result_collector.py:431,435`) naming what likely changed (var
   added/removed/renamed/reordered/re-unitted, diffed from the stored summary)
   and how many historical `over_time` events are orphaned under the old key.
2. **A note in the rendered report's over-time/history section** (the surfacing
   A4 §3.5 / W5 already call for) so a reset is not invisible to someone who only
   opens the HTML.
3. **The `on_history_reset` policy knob** below, which decides whether the
   mismatch is tolerated or fatal.

Add the escape hatch on `BenchRunCfg` (`bench_cfg.py:98`, next to `clear_history`
at `:348`): `on_history_reset = "warn" | "error" | "ignore"`, default `"warn"`
(emit 1+2). `"error"` raises a `HistoryResetError` naming the diff — for CI that
must never silently lose a baseline; `"ignore"` suppresses 1+2 for a deliberate
reset. Silent invalidation becomes observable without blocking legitimate resets.

## 3. Research questions (resolve before implementing)

1. **Can the `result_vars` contribution be made order-independent safely?** Result
   vars become xarray *data variables*, keyed by name and inherently unordered, so
   in principle yes. Confirm nothing depends on `result_vars` list order for
   *correctness* (display ordering should read the config list, not the cache
   key); grep for positional iteration over `result_vars`.
2. **Same for `const_vars`** — likely easier: constants create no dims and their
   order only feeds the title string (`bencher.py:448-452`). Canonicalize by name.
3. **Must `input_vars` stay ordered?** Input order determines the history array's
   dim order (`bench_cfg.py:1075`), and although xarray aligns by dim *name* (a
   transposed history may concat fine), positional code exists — `da.values[..., t_idx]`
   assumes `over_time` is the last axis (`result_collector.py:86-93`). Default:
   keep `input_vars` ordered; scope order-independence to `result_vars` + `const_vars`.
4. **Should the variable name be part of identity?** Including it turns a rename
   into a *clean, detected* full invalidation instead of a silent split (result
   vars) or broadcast corruption (input vars). Weigh against users who rename
   purely for display and want history kept — the current behavior does not keep
   it correctly anyway. Recommendation: include the name for input, result, and
   const vars, plus load-time reconciliation so the reset is reported.
5. **What must the D3 index store to produce a useful diagnosis?** Enough to
   classify rename vs reorder vs re-unit vs add/remove; decide its format and
   where it lives (history cache vs alongside `CACHE_VERSION`).
6. **Interaction with A4.** If A4 Phase C2 has introduced `bencher/caching/keys.py`,
   this fix belongs there. Otherwise implement in `bench_cfg.py` and leave a
   pointer for A4 to absorb (and flag A4's stale W5 wording to its owner).

## 4. Proposed direction (subject to the research above)

Treat the benchmark identity as an unordered set of *named* variables:

- Compute each result var's identity as `hash_sha1((rv.name, rv.hash_persistent()))`
  and each const's as `hash_sha1((cv.name, cv.hash_persistent(), hash_sha1(value)))`
  — name included fixes D2; value retained (a different constant is a different
  experiment).
- Combine result-var and const-var identities **order-independently** (fixes D1).
  Two candidate combiners, with the tradeoff spelled out so an implementer need
  not re-derive it:
  - **Sorted-tuple hash (recommended):** `hash_sha1(tuple(sorted(per_var_hashes)))`
    — sort the per-variable digests, then hash the tuple. Deterministic, preserves
    multiplicity (two vars sharing an identity stay two entries), trivially
    auditable, and reuses the existing `hash_sha1` primitive.
  - **Commutative/multiset hash:** an order-free operator (XOR or modular sum of
    the per-var digests). No sort, but XOR *cancels* duplicates (two identical
    identities collapse to 0) and additive sum is a weaker mixer with higher
    collision risk.

  Use the sorted-tuple hash: the sort cost is negligible (a handful of vars) and
  it has no cancellation failure mode — important because same-type vars already
  share an identity (§2), so a commutative combiner could silently zero them out.
- Keep `input_vars` folded in order, but include each var's name (pending
  research question 3).
- On history load, compare the stored dataset's data-variable *and dim* name sets
  against the current config; on mismatch, discard-and-report instead of
  outer-joining/broadcasting into a corrupt dataset (fixes D2's split and blow-up).
- Add the last-seen-key index + `on_history_reset` policy from D3.

This is a **cache-busting** change: bump `CACHE_VERSION` and headline it in the
CHANGELOG (a one-time miss for everyone, same policy A4 uses for its `code_hash`).

## 5. Acceptance criteria

- New tests, all passing:
  - reordering `result_vars` yields an identical `hash_persistent` (D1);
  - reordering `const_vars` (including dict-sourced) yields an identical hash (D1);
  - two same-type result vars — and two same-type input vars — with different
    names yield **different** per-var and benchmark hashes (D2);
  - set-equal result-var collections in any order share one key;
  - end-to-end `over_time` tests where a result var (then an input var) is renamed
    load with a *reported* history reset — no dead column, no phantom dim (D2/D3);
  - `on_history_reset`: `"warn"` (default) emits a WARNING naming the change and
    the orphaned-event count; `"error"` raises; `"ignore"` stays quiet (D3).
- The existing `hash_persistent` determinism-contract tests still pass.
- `CACHE_VERSION` bumped; CHANGELOG entry added.
- `pixi run ci` (and `pixi run test-split` if present) green.

## 6. What NOT to do

- Do not change the intentional exclusion of display-only fields (`title`) — A4 §5
  stands — nor add `direction`/`share_axis`/`max_time_events` back into the per-var
  hash: those `_hash_exclude` entries (`results.py:102-107`) are deliberate.
- Do not attempt to migrate or preserve existing pickled history across the key
  change; a one-time reset is the accepted recovery path for a cache.
- Do not make `input_vars` order-independent without first confirming no code
  relies on positional dim layout (research question 3).
- Do not default `on_history_reset` to `"error"` — first runs and intentional
  experiment changes are legitimate resets and must not hard-fail by default.
