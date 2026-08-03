# Plan 14 — Schema-Evolving over_time History (retain + projection)

**Status: IMPLEMENTED** (same PR as the plan-09 fixes; one shared `CACHE_VERSION`
bump). This document records the design and its rationale rather than
prescribing future work — read it before touching `bencher/history.py`,
`hash_persistent`, or `load_history_cache`.

**Goal:** let the set of result variables evolve — add, remove, reorder, or
deliberately redefine metrics — without orphaning a benchmark's accumulated
`over_time` history and regression baselines, while keeping every dataset a
consumer sees exactly congruent with the *current* benchmark definition.

Plan 09 made history resets correct and observable; this plan makes most of
them unnecessary. Downstream suites had grown folklore defenses against the
old behavior (routing every `result_vars` list through one shared constant;
documenting metrics as "deliberately omitted forever" because adding them
would reset another metric's history). When users build conventions around a
cache key, the key is wrong — plan 09 §"Read first" says the same.

## 1. The core tension this resolves

Two legitimate requirements pull the cache key in opposite directions:

- **Single-result coherency** (Layer B, `cachedir/benchmark_inputs`): a cached
  result must be exactly what the current definition would produce. Any
  result-var change must force a recompute → the key must include result vars.
- **History continuity** (Layer C, `cachedir/history`): `task_success`'s trend
  does not logically depend on whether `shutdown_time` was added next to it →
  the key must NOT include result vars.

The pre-existing design used one hash for both layers, forcing one semantics
onto both — the root cause of the tension. The fix is to split them:

- Layer B keys on `hash_persistent(True)` — strict, includes result vars
  (order-independently, per plan 09 D1).
- Layer C keys on `hash_persistent(True, include_result_vars=False)` —
  result-var differences are reconciled per column at load time.

Input vars and constants stay in *both* keys: a change to the input space is a
different experiment, and its history reset is clean and reported (plan 09 D3)
rather than reconciled. This also structurally rules out the phantom-dimension
broadcast corruption (plan 09 D2): datasets that reach `xr.concat` always have
identical non-`over_time` dims, and a defensive layout check discards (with a
report) rather than broadcasts if a hand-seeded record disagrees.

## 2. Retain + projection

`load_history_cache` stores a **record** `{format, dataset, columns, retired}`
where `dataset` is a *superset* holding every column ever measured, and serves
consumers a **projection** onto exactly the current config's columns
(`bencher/history.py:project`). Consequences:

- Every consumer — plotting (which iterates `dataset.data_vars`), regression
  detection, export — sees only current columns: the same invariant a
  destructive prune would give.
- Removal is non-destructive. A column whose variable left the config goes
  *dormant*: retained in the superset, invisible in the projection, resumed
  (with a NaN gap) if the variable returns with the same identity. A typo'd
  name in a shared result-var constant, a debug run with a reduced metric set,
  or an unmapped rename can therefore never destroy shared history — the worst
  case is a warning and a gap.
- The one widening operation is NaN-backfill of a newly born column. NaN gaps
  for non-NaN-sentinel column types (media "NAN", reference −1) are rewritten
  to the proper sentinel after concat so `result_is_missing` semantics hold.

## 3. Column identity and `meaning_version`

A column's identity is `(name, class, units, meaning_version)`
(`bencher/history.py:column_identity`). Name-keyed reconciliation cannot see a
metric that keeps its name but changes *meaning* — the worst corruption,
because splicing two different quantities into one trend defeats the point of
history. `meaning_version` (a `ResultFloat` field, default 1, hashed) is the
sanctioned way to declare that: bumping it *retires* the old column (kept in
the superset under a mangled name) and restarts the trend, while every other
column continues. Renames are remove+add by design; a rename that should keep
history is expressed as… not renaming, or accepting the restart.

Per-column birth coordinates are stamped on the served dataset
(`history_birth` DataArray attr) so "did not exist yet" is distinguishable
from "sample failed", and regression gating can hold fire while a baseline is
young: below `BenchRunCfg.regression_min_history` points since birth
(per-var override: a `min_history` key in `regression_overrides`), a
regression is reported and exported (`young_baseline: true`) but never
triggers `regression_fail`. History-free checks (`absolute` hard limits) gate
regardless — they need no baseline. The default (`1`) reproduces the previous
gating behavior exactly.

## 4. Observability (plan 09 D3, extended to columns)

All schema events route through `BenchRunCfg.on_history_reset`
(`warn`/`error`/`ignore`, default `warn`) *before* the record is persisted, so
an erroring CI run does not advance history state:

- lossy events — whole-history reset (key moved; diagnosed via a per
  `(bench_name, tag)` last-seen index storing the previous key and a config
  summary, diffed to name what changed and how many events are orphaned),
  column dormant, column retired, incompatible history discarded;
- informational events (column born, column resumed) always log at INFO.

## 5. What was deliberately NOT done

- **No reconciliation across input/const changes** — different experiment,
  clean reported reset. Do not "extend" reconciliation to dims; that path is
  where fabricated-data corruption lives.
- **No `renamed_from` continuity mapping** — renames restart the column;
  retained data makes that cheap to reverse. Add only with a concrete need.
- **No pruning / TTL of dormant columns** — they are NaN-cheap; deletion
  reintroduces the accidental-loss class this design removes. `max_time_events`
  still bounds the time axis for everything.
- **No migration of pre-v5 cache entries** — `CACHE_VERSION` bump, one-time
  miss, per the standing cache policy.
- **`meaning_version` only on `ResultFloat`/`ResultBool`** (scalar metrics with
  baselines). Other result types participate in identity with
  `meaning_version=None`; versioning a media column is expressed by renaming.
- **Report-page surfacing of history events** (plan 09 D3 item 2) — the
  events are logged and the policy knob exists; embedding them in the rendered
  report remains open (coordinate with A4 §3.5 / W5).

## 6. Key files

- `bencher/history.py` — identity, reconciliation, projection, policy.
- `bencher/bench_cfg.py` — `hash_persistent(include_repeats,
  include_result_vars)`; `on_history_reset`; `regression_min_history`.
- `bencher/result_collector.py` — `load_history_cache` orchestration,
  last-seen index, record persistence.
- `bencher/regression.py` — `young_baseline` on `RegressionResult`,
  `RegressionReport.has_blocking_regressions`, per-var `min_history`.
- `test/test_history_reconciliation.py` — lifecycle, policy, and gating tests;
  `test/test_hash_persistent.py` — golden hashes (updated for v5).
