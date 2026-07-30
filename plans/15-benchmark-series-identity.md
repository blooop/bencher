# Plan 15 — Stable Benchmark Series Identity

**Goal:** Let a benchmark's `over_time` history survive renames, and make every
identity change either *adopted* or *reported* — never silently orphaned. Today
the reset detector added in plan 09 is keyed on the two fields whose change is
the most common cause of a reset, so it cannot see them move.

**Branch name:** `feat/benchmark-series-identity`

**⚠️ Read first:** plans 09 and 14 (both implemented in v1.116.0) define the
history key and the reconciliation model this builds on. The new field must not
enter `hash_persistent()` (`bencher/bench_cfg.py:785`) — it identifies a
*series*, not a configuration, and folding it in would re-key every existing
cache and history on upgrade.

---

## Problem statement (with evidence)

### P1 — The reset detector is keyed on the fields it exists to detect

Plan 09 shipped a last-seen index so a moved history key is reported rather
than silently starting a new trend. On a history-cache miss the loader looks up
the previous entry, compares keys, and emits a `full_reset` event naming the
diff (`bencher/result_collector.py:508-520`), which `apply_policy` then warns
or raises on (`bencher/result_collector.py:546`, `bencher/history.py:405`).

That index is keyed by `last_seen_key(bench_name, tag)`
(`bencher/history.py:180`), and both of those are themselves inputs to the
history key (`bencher/bench_cfg.py:831` folds `bench_name`, `:834` folds
`tag`). So the detector splits cleanly in two:

| What changed | Index entry | Detected? |
|---|---|---|
| `input_vars`, `const_vars`, `repeats` | stays put | **yes** — `full_reset` with a diff |
| `bench_name` or `tag` | **moves with the key** | **no** — miss on both, silent orphan |

A rename is the *most likely* way a key moves in practice, and it is precisely
the case that produces no event: the lookup at
`bencher/result_collector.py:510` misses, so the code takes the "first run ever"
path and writes a fresh index entry under the new name.

### P2 — `bench_name` defaults to a Python class name, and it is hashed

When a sweep is turned into a bench without an explicit name, the name falls
back to the worker's class name (`bencher/factories.py:39-42`, reached from
`ParametrizedSweep.to_bench` at `bencher/variables/parametrised_sweep.py:246`).
That value is then folded into the persistent hash
(`bencher/bench_cfg.py:831`).

The consequence is that ordinary refactors silently reset history: renaming the
worker class, extracting a shared base and running it under two thin
subclasses, or generating worker classes programmatically all change the
identity of a benchmark whose measurements did not change at all. Plan 13's D3
recognizes exactly this hazard for `__name__`-derived *tags* and deliberately
gates auto-tagging on the decorator so undecorated benchmarks are not re-keyed;
the same hazard already exists, ungated, for `bench_name`.

### P3 — `tag` carries two unrelated jobs

`tag` is the sample-cache isolation knob — the effective cache tag is
`run_cfg.run_tag + tag`, composed at `bencher/bencher.py:524` and again on the
`optimize()` path at `bencher/bencher.py:1224` — *and* part of series
identity. So a change made for cache-partitioning reasons resets the trend, and
there is no way to express "different cache partition, same series" or "same
partition, deliberately new series".

### P4 — There is no way to say "this is the same benchmark as before"

Because identity is derived entirely from incidental facts (a class name, a
cache tag), an author who *intends* continuity across a refactor has no way to
declare it, and an author who intends a fresh start has no way to declare that
either. Both are expressed by accident, and neither is visible in review.

---

## Proposed design

One new author-controlled field, used as the index key and nothing else.

### D1 — `series_id` on the sweep declaration

`plot_sweep()` gains `series_id: str | None = None`
(`bencher/bencher.py:271-288`), stored on `BenchCfg` and defaulting to
`f"{bench_name}:{tag}"` — byte-identical to today's index key, so nothing moves
on upgrade.

- It **must not** reach `hash_persistent()` (`bencher/bench_cfg.py:785`). That
  method folds an explicit tuple of fields rather than scanning the class, so
  exclusion means simply not adding it — and unlike the sweep-variable classes
  there is no slot-coverage test to catch a mistake here, which is why phase 1
  lands a golden-hash guard before anything else. Two benchmarks with the same
  inputs, consts, name, and tag stay one cache entry whatever their
  `series_id`; the field decides only *which trend line this run appends to*.
- The last-seen index key becomes `last_seen_key(series_id)`
  (`bencher/history.py:180`), with the legacy two-argument form retained for one
  release as a read fallback (see D4).
- `series_id` is also a natural member of plan 13's declaration bundle, so it
  can be declared once per benchmark rather than at each call site.

### D2 — Adopt history across a pure rename

With a stable `series_id`, a moved key can be classified instead of guessed at.
The index entry already stores a `config_summary` — inputs, consts, results,
repeats (`bencher/history.py:135-152`) — so on a cache miss under a known
`series_id`:

| Stored summary vs current | Classification | Action |
|---|---|---|
| identical | pure rename (`bench_name`/`tag` moved) | **adopt**: re-key the stored record to the new hash, emit `history_renamed` |
| differs | genuine new experiment | **reset**: today's `full_reset` event, with the existing diff |

Adoption is safe exactly when the summary matches, because the summary covers
every field that shapes the dataset: same dimensions, same coordinates, same
columns. The record is moved, not merged — no concatenation of incompatible
datasets, which is the failure class plan 14 was written to avoid.

`history_renamed` is a new `HistoryEvent` kind. It is **informational**, not
loss-y: `apply_policy` (`bencher/history.py:405`) should log it at INFO and not
raise even under `on_history_reset="error"`, because nothing was lost. Only the
reset branch stays fatal under that policy.

### D3 — Separate cache partition from series

Once `series_id` exists, a caller who changes `tag` purely to isolate a cache
partition keeps `series_id` fixed and keeps the trend. Document the pairing
explicitly at both fields: **`tag` partitions storage, `series_id` names the
trend.** No behavior change for callers who set neither.

### D4 — Upgrade path

The first run after upgrade must find its predecessor. Order the lookup:

1. `last_seen_key(series_id)` — the new form.
2. `last_seen_key(bench_name, tag)` — the legacy form, read-only.

A hit on (2) is migrated by writing (1) and is not reported as an event. Drop
the fallback after one minor release, noted in `CHANGELOG.md`.

---

## Phased steps

Each phase is independently shippable and leaves the suite green.

1. **Add the field, keep the behavior.** `series_id` on `plot_sweep`/`BenchCfg`,
   defaulted to `f"{bench_name}:{tag}"`, added to `_hash_exclude`, with a
   `test_hash_persistent.py` case proving the golden hashes are unmoved
   (`test/test_hash_persistent.py:774-801`).
2. **Re-key the index.** Index on `series_id` with the legacy read fallback
   (D4). No new events yet; existing `full_reset` detection must behave
   identically for unchanged benchmarks.
3. **Add adoption.** The summary comparison, the `history_renamed` event, the
   record move, and the INFO-level policy handling.
4. **Documentation.** The `tag`-vs-`series_id` split at both fields, in the
   caching docs, and a `CHANGELOG.md` entry stating that renaming a worker class
   no longer resets history when `series_id` is declared.
5. *(Optional, after plan 13)* accept `series_id` in the declaration bundle.

---

## Tests / acceptance criteria

- Golden hashes in `test/test_hash_persistent.py` are unchanged by phase 1.
- Two runs differing only in `bench_name`, same `series_id`: second run adopts,
  history length grows by one, a `history_renamed` event is emitted, and
  `on_history_reset="error"` does **not** raise.
- Same, differing only in `tag`: same outcome.
- Two runs differing in `input_vars` under one `series_id`: `full_reset` with
  the existing diff text; `on_history_reset="error"` raises and the stored
  record is left untouched (the pre-persist guarantee from plan 14).
- A run whose index entry exists only under the legacy key migrates silently
  and reports no event.
- `series_id` never reaches the hash: a new case alongside
  `test_title_change_does_not_affect_golden_hash`
  (`test/test_hash_persistent.py:796`) asserting that two configs differing only
  in `series_id` share both the cache key and the history key.

## Migration & compatibility

Fully backward compatible. Callers who set nothing get today's identity, today's
detection, and one extra INFO line's worth of behavior change (renames that were
previously silent orphans become silent *adoptions* only if they also happen to
share a default `series_id` — which they do not, so unchanged callers see no
difference at all). The stored record layout gains no new required field;
`HISTORY_FORMAT` (`bencher/history.py:59`) needs a bump only if the record
itself grows `bench_name`/`tag` provenance, which D2 requires — do it in phase 3
with the reconciliation loader tolerating a missing field.

## Risks

- **Adoption of the wrong record.** Mitigated by requiring an exact
  `config_summary` match; a mismatch falls through to today's reset path.
  A hand-copied `series_id` shared by two genuinely different benchmarks would
  produce a reset on every alternating run, which is noisy but not corrupting.
- **`series_id` drifting into the hash.** A single misplaced line would re-key
  every user's cache. The `_hash_exclude` contract test is the guard, and phase 1
  exists specifically to land that guard before any behavior changes.
- **Scope creep into A4.** This plan touches only the last-seen index and the
  record's identity fields; storage layout stays A4's business.

## Coordination

- **Plan 09** introduced the last-seen index; this closes the hole in it.
- **Plan 14** owns the reconciliation model — adoption must not bypass it.
- **Plan 13** D1/D3: `series_id` belongs in the declaration bundle, and D3's
  gating of `__name__`-derived tags shares this plan's reasoning.
- **Plan 16** exposes identity as an inspectable value; the two are independent
  but land better together (16 makes this plan's behavior assertable).
- **A4** may relocate the index; keep the key derivation in one function
  (`bencher/history.py:180`) so it moves as a unit.
