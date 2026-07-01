# Plan 04 — Dependencies & Import Time

**Goal:** Close the diskcache CVE, fix nonsensical version floors, document the pickle
boundary, and reduce import time by lazy-loading heavy libraries.

**Prerequisite:** Plan 02 step 2 (PR #760, diskcache → minimalkv). If #760 is merged,
skip Task 1 here. If #760 was closed instead, Task 1 becomes redoing that work — stop
and ask the owner before attempting that from scratch.

**Branch name:** `deps/tighten-and-lazy-import`

---

## Task 1: diskcache CVE-2025-69872 (only if PR #760 is still open/unresolved)

Coordinate with plan 02 — do not duplicate the work. If neither is possible, at minimum
add a note to README.md's install section: "bencher currently depends on diskcache
<= 5.6.3, which has a known pickle-deserialization CVE (CVE-2025-69872). Only use cache
directories you created yourself."

## Task 2: Fix the `numpy>=1.0` floor

In `pyproject.toml` dependencies, `numpy>=1.0,<=2.4.6` would accept a 2006 release.

1. Change it to `numpy>=2.0,<=2.4.6` (2.0 is a reasonable tested floor given the
   pandas>=2.0 / xarray>=2023.7 companions).
2. Run `pixi install` to refresh `pixi.lock`, then `pixi run test`. Commit both files.

Do NOT change any other bounds in this task — the remaining upper pins follow the
project's existing "pin to latest known-good" convention and are updated by dependabot.

## Task 3: Pickle-boundary warning docstring

`bencher/render.py` deserializes pickled `BenchResult` files. Add a warning to the
`load_result` function's docstring:

```
Warning:
    This deserializes pickle data, which can execute arbitrary code. Only load
    result files that your own benchmark process saved via ``save_result``.
    Never load result files from untrusted sources.
```

Verify with `pixi run python -c "import bencher; help(bencher.load_result)"`.

## Task 4: Lazy-import heavy libraries in core modules

**Context:** Plotly and `optuna.visualization` were already made lazy (commit 37b28808).
Remaining eager imports that cost startup time: `panel`, `optuna`, and the holoviews
chain, pulled in at module level by `bencher/bencher.py` and `bencher/bench_report.py`.

**Approach — do this incrementally, one library per commit:**

1. Measure the baseline first and record it in the commit message:

   ```bash
   pixi run python -c "import time; t=time.time(); import bencher; print(f'{time.time()-t:.2f}s')"
   ```

2. For `optuna` in `bencher/bencher.py`: remove the top-level `import optuna`, and add
   `import optuna` inside each function that uses it (search `optuna\.` within the file).
   Mirror the existing lazy-import style used for plotly (see commit 37b28808 and the
   comment style around it).
3. Run the full suite after each library: `pixi run test`. Also run the split-render
   suite once at the end: `pixi run test-split` (slow).
4. For `panel` in `bencher/bencher.py` / `bencher/bench_report.py`: this is harder
   because `pn` types may appear in signatures/defaults. Only convert call sites where
   `pn` is used purely inside function bodies. If a module uses `pn` in class-level or
   signature positions, leave that module alone and note it in the report.
5. Re-measure import time. If a change yields <5% improvement and added complexity,
   revert that change — lazy imports have a readability cost.

**Do NOT** attempt to make `param`, `xarray`, or `pandas` lazy — they are used
pervasively at class-definition time and the attempt will fail.

## Task 5 (OWNER DECISION — propose, don't implement): core/viz extras split

Write a short proposal comment in the PR description (not code): splitting dependencies
into a minimal core and a `[viz]` extra (holoviews, panel, hvplot, plotly, matplotlib)
would let CI/headless users install without ~200MB of plotting stack. It is a breaking
change for `pip install holobench` users if the default loses viz, so the owner must
choose between `holobench[viz]` opt-in vs viz-by-default with a `holobench-core` variant.

## Final verification

```bash
pixi run ci
pixi run test-split
pixi run python -c "import time; t=time.time(); import bencher; print(f'{time.time()-t:.2f}s')"
```

Include before/after import times in the PR description.
