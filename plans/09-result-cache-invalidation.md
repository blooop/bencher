# Plan 09 — Result Cache & History Invalidation Correctness

**Goal:** Fix two correctness defects in how the benchmark-config hash
(`BenchCfg.hash_persistent`) invalidates the result cache (Layer B) and the
`over_time` history cache (Layer C):

1. It is **sensitive to the order** of `result_vars`, so reordering the result
   columns — a change that alters nothing about *what* is measured — silently
   discards a benchmark's entire accumulated history and regression baselines.
2. The per-variable hash **excludes the variable name**, so *renaming* a result
   variable does not change the key, yet the stored history is keyed internally by
   name. The result is a silent, partial history split rather than a clean reset.

**⚠️ Read first:** This plan deliberately revisits `hash_persistent()` *semantics*,
which `plans/architecture/A4-caching-architecture.md` §5 says NOT to change. A4's
"don't touch it" refers to the intentional exclusion of display-only fields (e.g.
`title`) — that guidance stands. The ordering/naming behavior described here is a
*different* thing: a genuine defect, not an intentional exclusion. Coordinate with
A4: if A4 Phase C2 (the `bencher/caching/keys.py` key module) has already landed,
implement this fix there instead of in `bench_cfg.py`.

**Rules:**
- Always use the pixi environment (`pixi run ...`, e.g. `pixi run pytest`). Never
  run tools directly.
- Work on a feature branch, never `main` (merging to `main` with a version bump
  auto-publishes to PyPI — see plans/01).
- The `hash_persistent()` determinism contract (the auto-discovering determinism
  tests) must still hold: identical configs → identical hash across processes.
- Any change to a cache key is cache-busting. Bump `CACHE_VERSION` in the same PR
  and add a headline CHANGELOG entry. Do not attempt to migrate pickled legacy
  entries — a one-time miss is the accepted recovery path.
- If a step fails in a way this plan does not cover, stop and report rather than
  improvising.

---

## 1. Background — where the key is used

`BenchCfg.hash_persistent(include_repeats)` (`bencher/bench_cfg.py:757`) is the
persistent identity of a benchmark run. Two on-disk caches key on it:

- **Layer B — result cache** (`bencher/result_collector.py`, `cachedir/benchmark_inputs`):
  keyed by `hash_persistent(include_repeats=True)`.
- **Layer C — `over_time` history** (`bencher/result_collector.py:399`
  `load_history_cache`, `cachedir/history`): keyed by
  `hash_persistent(include_repeats=False)`. Each run loads `ds_old = cache[cfg_hash]`
  and does `xr.concat([ds_old, dataset], "over_time")`. A missing key means "no
  history" → the series starts fresh.

Crucially, the history dataset's *data variables* are named by each result var's
`.name` (`add_metadata_to_dataset`: `bench_res.ds[rv.name]`). So a metric's identity
*inside the history* is its **name**, while its identity *in the cache key* is its
**type/units/direction** (see §2). Those two notions of identity disagree — that
mismatch is the root of defect D2.

## 2. The defects

### D1 — `result_vars` order changes the key (it should be a no-op)

`hash_persistent` folds each variable into a running accumulator **in list order**
(`bench_cfg.py:796-798`):

```python
all_vars = (self.input_vars or []) + (self.result_vars or [])
for v in all_vars:
    hash_val = hash_sha1((hash_val, v.hash_persistent()))
```

The fold is a non-commutative chained hash, so permuting `result_vars` changes the
final hash whenever the permuted vars have distinct `hash_persistent()` values
(i.e. distinct class/units/direction — see D2). The *set* of measured quantities is
unchanged, yet both Layer B and Layer C miss, and the benchmark's entire history
and regression baselines are silently dropped.

The intuitive mental model is that a benchmark's result vars are a *set* and their
order is a presentation detail (column order). Nothing documents that reordering is
a full invalidation event, and the determinism tests only assert *same input → same
hash*, never *reordered-but-equivalent input → same hash*.

**Reproduction** (add as a failing test, then make it pass):

```python
import bencher as bn
from bencher.bench_cfg import BenchCfg
from bencher.variables.results import OptDir

def key(result_vars):
    c = BenchCfg()
    c.bench_name = "demo"
    c.tag = "demo"
    c.over_time = True
    c.input_vars = []
    c.result_vars = result_vars
    return c.hash_persistent(include_repeats=False)

a = bn.ResultBool(units="ratio", direction=OptDir.maximize)
b = bn.ResultFloat(units="s", direction=OptDir.minimize)

assert key([a, b]) == key([b, a])   # FAILS today: reordering invalidates history
```

### D2 — the per-variable hash ignores the variable name

`_hash_slots` (`bencher/variables/results.py:50`) hashes the concrete class name
plus the values of every `__slots__` declared on bencher's own Result classes
(units, direction, bounds, …), and stops walking the MRO at the param framework —
so the Parameter's `name` is never hashed. Two result vars with the same
class/units/direction but different names produce identical `hash_persistent()`.

Consequences:

- **Renaming a result var does not change the benchmark key.** Layer C still finds
  `ds_old`, but `ds_old` holds a data variable under the *old* name while the fresh
  run produces the *new* name. `xr.concat([ds_old, dataset], "over_time")`
  outer-joins them: the renamed metric appears as a new column holding only the
  latest point (looks reset), while the old-named column persists as a dead column
  that never receives new data. This is a silent partial corruption — worse than a
  clean reset.
- Conversely, this is *why* D1's fix is safe for same-type vars: they are already
  indistinguishable to the key, so only reorders of *distinct-type* vars move it.

**Reproduction** (names are normally bound via class-attribute declaration; set
directly here to isolate the hash behavior):

```python
import bencher as bn
from bencher.variables.results import OptDir

x = bn.ResultFloat(units="s", direction=OptDir.minimize); x.name = "duration"
y = bn.ResultFloat(units="s", direction=OptDir.minimize); y.name = "latency"

assert x.hash_persistent() != y.hash_persistent()  # FAILS today: rename is invisible to the key
```

### D3 — invalidation is silent

When the key changes (D1) or the concat mismatches (D2), history vanishes or splits
with only a debug/`info`-level log. A user cannot distinguish an intended reset from
an accidental one. (A4 §3.5 / W5 already argue for *reporting* history
incompatibilities; D2 is a concrete case that should surface to the user.)

## 3. Research questions (resolve before implementing)

1. **Can the `result_vars` contribution be made order-independent safely?** Result
   vars become xarray *data variables*, which are keyed by name and inherently
   unordered, so in principle yes. Confirm nothing downstream depends on
   `result_vars` list order for *correctness* — only for display ordering, which
   should read the config list directly, not the cache key. Grep for places that
   iterate `result_vars` and assume positional meaning.
2. **Must `input_vars` stay ordered?** Input vars become xarray *dimensions*, and
   dimension order can matter (coordinate layout, some reductions/reshapes). Decide
   whether input order is part of identity (likely yes) or can also be
   canonicalized. Default recommendation: make only the `result_vars` contribution
   order-independent; keep `input_vars` ordered unless research proves order is
   irrelevant.
3. **Should the variable name be part of identity?** Including the name in the
   per-var hash turns a rename into a *clean, detected* full invalidation (one-time
   reset) instead of a silent split. Weigh against users who rename a column purely
   for display and want history kept — but note the current behavior does not keep
   it correctly (it produces a dead column). Recommendation: include the name, and
   add the load-time reconciliation from A4 §3.5 so the reset is reported.
4. **Interaction with A4.** If A4 Phase C2 has introduced `bencher/caching/keys.py`,
   this fix belongs there. Otherwise implement in `bench_cfg.py` and leave a pointer
   for A4 to absorb.

## 4. Proposed direction (subject to the research above)

Treat the benchmark identity as an unordered set of *named* result variables:

- Compute each result var's identity as `hash_sha1((rv.name, rv.hash_persistent()))`
  (name included → fixes D2).
- Combine the result-var identities **order-independently** — e.g. fold the
  *sorted* tuple of per-var identity hashes, or use a commutative combiner — so any
  permutation collapses to one key (fixes D1).
- Keep `input_vars` folded in order (pending research question 2).
- On history load, compare the stored dataset's data-variable set against the
  current result-var names; if they differ, discard-and-report instead of
  outer-joining into a corrupt dataset (fixes D2's split and D3's silence).

This is a **cache-busting** change: bump `CACHE_VERSION` and headline it in the
CHANGELOG (a one-time miss for everyone, same policy A4 uses for its `code_hash`).

## 5. Acceptance criteria

- New tests, all passing:
  - reordering `result_vars` yields an identical `hash_persistent` (D1);
  - two same-type result vars with different names yield **different** per-var and
    benchmark hashes (D2);
  - set-equal result-var collections in any order share one key;
  - an end-to-end `over_time` test where a result var is renamed loads with a
    *reported* history reset, not a phantom dead column (D2/D3).
- The existing `hash_persistent` determinism-contract tests still pass (same config
  → same hash across processes).
- `CACHE_VERSION` bumped; CHANGELOG entry added.
- `pixi run ci` (and `pixi run test-split` if present) green.

## 6. What NOT to do

- Do not change the intentional exclusion of display-only fields (`title`) — that
  part of A4 §5 stands.
- Do not attempt to migrate or preserve existing pickled history across the key
  change; a one-time reset is the accepted recovery path for a cache.
- Do not make `input_vars` order-independent without first confirming
  dimension-order independence.
