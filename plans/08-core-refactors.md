# Plan 08 — Larger Core Refactors

**Goal:** Reduce the three biggest structural debts: `bencher/bencher.py` (1,516 lines,
46 methods), `bencher/bench_cfg.py` (1,060 lines, 100+ params), and
`bencher/regression.py` (1,448 lines mixing statistics and rendering).

**⚠️ Read first:** These are the highest-risk plans in the set. Each subsection is an
independent PR. Get owner sign-off on the approach **before** starting any of them —
especially Task 2, which overlaps with the proposal in open PR #923. Execute only after
plans 01 (CI gates), 05 (test coverage), and 07 (cleanup) are done, so regressions are
caught.

**Rules for all tasks:**
- Behavior-preserving only. No public API removals; use the existing deprecation-alias
  mechanism (`__getattr__` in `bencher/__init__.py`) for any rename.
- `pixi run ci` AND `pixi run test-split` must pass after every commit.
- If a step requires touching more than ~3 files beyond what the task lists, stop —
  the task's assumptions are wrong; report instead of pushing through.

---

## Task 1: Extract regression rendering from `bencher/regression.py`

**Why:** The module mixes statistical detection (Hampel filter, slope fitting,
percentage/adaptive detection) with holoviews/matplotlib rendering and markdown
formatting. Splitting it halves the module and isolates the plotting dependencies.

**Steps:**

1. Read `bencher/regression.py` end to end. Classify every top-level function/class as
   DETECTION (math, no plotting imports), RENDERING (builds holoviews overlays /
   matplotlib PNGs), or REPORTING (markdown/summary strings).
2. Create `bencher/regression_rendering.py`. Move the RENDERING functions there
   verbatim (e.g. `build_regression_overlay`, `render_regression_png` — confirm exact
   names from the file). Move the holoviews/matplotlib imports with them.
3. In `bencher/regression.py`, re-export the moved names
   (`from .regression_rendering import build_regression_overlay, ...`) so all existing
   imports keep working. Check actual usage: `grep -rn "from.*regression import\|regression\." bencher/ test/ --include="*.py" | grep -v "regression_rendering"`.
4. Run the dedicated suite: `pixi run pytest test/test_regression.py -q` (115 tests),
   then full `pixi run ci`.

**Risk:** Low-medium. Pure file move with re-exports.

## Task 2: Split `BenchCfg` parameter groups (aligns with PR #923)

**OWNER DECISION REQUIRED FIRST.** Open PR #923 proposes a *non-backward-compatible*
nested-config redesign. This task is the backward-compatible alternative: introduce
grouped sub-config objects while keeping flat attribute access working. The owner must
pick: (a) this compatible path, (b) #923's clean break, or (c) defer entirely.

If (a) is chosen:

1. In `bencher/bench_cfg.py`, identify the parameter groups by reading the existing
   ordering/comments: execution, caching, display/printing, plotting, time/history,
   regression.
2. Start with ONE group only — caching (`cache_results`, `cache_samples`, `clear_cache`,
   `clear_sample_cache`, `overwrite_sample_cache`, `only_hash_tag`; confirm the full set
   by grepping `cache` in the class).
3. Create `class CacheCfg(param.Parameterized)` holding those params with identical
   names, defaults, and docs.
4. Keep the flat params on `BenchCfg` as the source of truth for now; add
   `cache: CacheCfg` as a *view* that reads/writes the flat params (properties), OR
   invert it — pick whichever produces the smaller diff. The acceptance criterion is:
   every existing access pattern (`bench_cfg.cache_samples`) still works and every test
   passes unmodified.
5. Run `pixi run ci` + `pixi run test-split`. Get the PR reviewed before doing any
   further group — the first group validates the pattern.

**Risk:** Medium-high. param inheritance and kwargs-construction
(`BenchRunCfg(**kwargs)`) paths are subtle. Stop and report if tests start needing edits.

## Task 3: Extract sweep orchestration from `Bench`

**Why:** `Bench` already delegates to `WorkerManager`/`SweepExecutor`/`ResultCollector`,
but the orchestration flow (`run_sweep`, `_append_result_via_split`, dataset setup,
history-cache loading, result storage) still lives in the 1,516-line class.

**Steps:**

1. Map the methods: in `bencher/bencher.py`, list every method between `run_sweep` and
   the result-storage helpers (the review identified roughly lines 617–903: `run_sweep`,
   `_append_result_via_split`, `load_history_cache`, `setup_dataset`,
   `define_const_inputs`, `define_extra_vars`, `calculate_benchmark_results`,
   `store_results` — confirm names against the current file).
2. Create `bencher/sweep_orchestrator.py` with a `SweepOrchestrator` class that takes
   the `Bench` instance's collaborators (worker manager, executor, collector, report) in
   its constructor. Move the method bodies; on `Bench`, keep thin one-line delegating
   methods with identical signatures (the codebase already uses this exact pattern —
   see the existing thin wrappers around lines 806–872).
3. Move methods one or two at a time, running `pixi run pytest test/test_bencher.py -q`
   between moves. Full `pixi run ci` + `pixi run test-split` at the end.

**Risk:** Medium. Mostly mechanical because the delegation pattern already exists.

## Task 4 (proposal only): Trim the public API surface

`bencher/__init__.py` exports ~165 names including internals (`PltCntCfg`,
`hash_sha1`, `MethodCells`). Do NOT remove anything. Instead produce a written audit:
for each export, count usages outside the package
(`grep -rn "bn\.<name>\|bencher\.<name>" docs/ bencher/example/ | wc -l`) and propose a
keep/deprecate list in a markdown table for owner review. Deprecations, if approved,
go through the existing `_DEPRECATED_ALIASES` + `__getattr__` mechanism in a later PR.

## Final verification (per task)

```bash
pixi run ci
pixi run test-split
```

Each PR description must state which task it implements, confirm zero public API
changes, and list any deviations from this plan.
