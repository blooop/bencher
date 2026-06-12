# Plan 05 — Test Coverage Gaps

**Goal:** Add direct unit tests for the untested `bencher/results/` modules and core
modules, remove flakiness sources, and resolve long-skipped tests. The suite currently
has ~90% line coverage but ~27 result/rendering modules are only exercised indirectly
through generated-example integration tests, so axis/label/layout bugs surface late.

**Branch name:** one branch per task group, e.g. `test/results-unit-tests`,
`test/fix-file-server-flake`.

**How to write tests here:** follow the style of the strongest existing test files —
`test/test_render.py` (behavioral assertions on round-trips and object counts) and
`test/test_regression.py` (per-method test classes with edge cases). Tests must assert
behavior (values, labels, limits, shapes), not just "no exception was raised" — though
for pure render paths a smoke test is an acceptable first step.

---

## Task 1: Unit tests for untested result modules

Work through this list **one module per commit**, highest value first:

| Priority | Module | What to test |
|----------|--------|--------------|
| 1 | `bencher/results/bench_result.py` | container behavior: `to_pane` paths, callback handling |
| 2 | `bencher/results/histogram_result.py` | binning, axis labels, NaN handling (NaN is now the missing-value default) |
| 3 | `bencher/results/optimize_result.py` | output structure for single/multi-objective |
| 4 | `bencher/results/dataset_result.py` | dataset viewer construction from a small sweep |
| 5 | `bencher/results/holoview_results/{scatter,bar,curve,band,table}_result.py` | one file per type: title/label propagation, dims mapping |
| 6 | `bencher/results/holoview_results/distribution_result/*.py` | box/violin/jitter construction with repeats>1 |
| 7 | `bencher/results/volume_result.py` | 3-float-input volume construction |
| 8 | `bencher/results/composable_container/composable_container_dataframe.py` | composition behavior |

**Recipe for each module:**

1. Find a generated example that exercises the module:
   `grep -rln "<ResultTypeName>" bencher/example/generated/ | head -3` — its source shows
   a minimal working sweep config for that result type.
2. Create `test/test_<module_name>.py`. Build the smallest sweep that produces the
   result type (1 input var, few samples, `repeats=1` unless testing distributions).
   Run it with `run_cfg` caching disabled and `auto_plot=False` where possible, then
   call the module's render/to_* method directly.
3. Assert at least: (a) the returned object is the expected pane/element type,
   (b) a known label/title string appears where the API promises it,
   (c) NaN/missing inputs don't crash (pass a worker that returns NaN for one point).
4. Run: `pixi run pytest test/test_<module_name>.py -q` then the full `pixi run test`.

Skip a module (and say so in the report) if constructing it requires optional deps
that aren't in the test env (e.g. `rerun_result.py` needs rerun-sdk, manim modules
need manim).

## Task 2: Unit tests for untested core modules

Same recipe, for:

- `bencher/bench_cfg.py` — test default values, that `over_time`/`repeats`/cache flags
  round-trip through construction, and the describe/summarise helpers if present.
- `bencher/worker_job.py` — construct a job, check kwargs/hash behavior.
- `bencher/video_writer.py` — core write path with a tiny synthetic frame array
  (2 frames of 8x8 pixels), assert the output file exists and is non-empty.

## Task 3: De-flake `test/test_file_server.py`

It uses `time.sleep(0.3)` before HTTP requests. Replace each sleep with a poll loop that
attempts a socket connection to the server port (timeout ~5s, step 0.1s) and raises
`TimeoutError` on failure. Then prove stability:

```bash
for i in $(seq 1 10); do pixi run pytest test/test_file_server.py -q || break; done
```

All 10 runs must pass.

## Task 4: Resolve long-skipped tests

1. `test/test_combinations.py` — the file is an empty placeholder. Delete it.
2. `test/test_sweep_vars.py::test_missing_default_value` (`@pytest.mark.skip`) — read the
   test and the code it targets. Since v1.105 flipped missing defaults to NaN, the test's
   premise may be obsolete: either rewrite it against the NaN behavior or delete it with
   a commit message explaining why.
3. `test/test_bencher.py::test_plot_all_permutations` — skipped due to "name collisions".
   Do NOT try to fix the underlying unique-name issue in this plan; instead change the
   bare `@pytest.mark.skip()` to
   `@pytest.mark.skip(reason="name collisions across permutations; see plans/05-test-coverage.md task 4")`
   so the debt is self-describing.
4. `test/test_usability.py` uses the deprecated `bn.ResultVar` — change it to
   `bn.ResultFloat` (run the test before and after to confirm identical behavior).

## Final verification

```bash
pixi run ci
pixi run coverage && pixi run coverage-report
```

Report the coverage delta (before → after) in the PR description. If plan 01's
`fail_under` is in place, consider raising it to match the new floor.
