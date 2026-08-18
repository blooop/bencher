# Tracking Results Over Time

Set `time.over_time=True` and each run of a benchmark appends a snapshot to a stored history
instead of replacing it. The report then gains a time slider you can scrub through, so you
see not just what the sweep measured but how that measurement has moved.

## What it does

A normal sweep produces one N-dimensional dataset. With `over_time` enabled, bencher adds a
time dimension: every `plot_sweep()` call records the whole grid at one point in time and
merges it with the history loaded from `cachedir/history`. The plots become a
[HoloViews](https://holoviews.org/) `HoloMap` keyed on that dimension, driven by a slider.

The history is keyed *without* result variables, deliberately. Adding or removing a metric
reconciles per column — new columns are NaN-backfilled and birth-stamped, removed columns
go dormant and resume if the variable comes back with the same identity — rather than
orphaning the entire trend. What *does* re-key the history is a change to the benchmark's
identity: bench name, input variables, const variables, tag, `time.over_time`, or
`execution.repeats`.

## When to use it

- **CI trend tracking.** One snapshot per commit or per nightly run, so a slow regression
  shows up as a drift rather than as a single surprising number.
- **Long studies.** A physical setup that is re-measured over days or weeks, where the
  interesting axis is the calendar and not any swept parameter.
- **Detecting whether noise or drift dominates.** With `repeats` also enabled, the Optuna
  importance analysis ranks `repeat` and `over_time` alongside your actual inputs, which
  tells you whether run-to-run noise or genuine temporal change is the larger effect.

If you only want a single report of a single sweep, leave `time.over_time` off — it costs a
history load, a merge, and a slider.

## Recording snapshots

The simplest form passes `over_time=True` to `bn.run()`:

```python
bn.run(MyBench, subsampling_divisions=3, repeats=3, over_time=True)
```

For multiple snapshots in one process — a CI pipeline replaying several commits, or a test
that needs a populated history — call `plot_sweep()` in a loop with a distinct `time_src`
each iteration. This is the pattern the generated gallery examples use, copied here from
`bencher/example/generated/1_float/over_time/example_sweep_1_float_0_cat_over_time.py`:

```python
def example_sweep_1_float_0_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = SortBenchmark()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.cache.clear = True
        run_cfg.time.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["array_size"],
            result_vars=["time"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench
```

Three details carry the whole pattern:

- `time_src` labels the snapshot. A `datetime` works, and so does a string —
  `bn.git_time_event()` produces one from the repository so snapshots are labelled by
  commit.
- `time.clear_history=True` on the **first** iteration only, so the loop starts from a known
  empty history instead of appending to whatever a previous run left behind.
- `cache.clear=True` forces re-evaluation. Without it the benchmark-level result cache
  would hand back the previous snapshot's numbers and every time point would be identical.
  See [Caching](caching.md).

Instead of `time_src`, you can set `run_cfg.time.event` — "a string representation of a
sequence over time, i.e. datetime, pull request number, or run number". When it is set it
takes precedence over the `time_src` argument.

### Controlling history size and the slider

These live on `BenchRunCfg`'s `time` sub-config (a `TimeCfg`), reached as
`run_cfg.time.<name>`:

| Parameter | Default | What it does |
|---|---|---|
| `time.over_time` | `False` | "If true each time the function is called it will plot a timeseries of historical and the latest result." |
| `time.clear_history` | `False` | "Clear historical results" |
| `time.max_events` | `None` | "Maximum number of over_time events to retain. Oldest events are trimmed. Set to None for unlimited." |
| `time.max_slider_points` | `10` | "Maximum number of time points shown in the over_time slider. Evenly subsampled (first and last always included). The aggregated tab still uses all data. Defaults to 10 to cap embed cost. Set to None for no subsampling." |
| `time.show_aggregated_tab` | `False` | "When over_time is active, show an 'All Time Points (aggregated)' tab alongside the per-time-point slider. Defaults to False for performance. Set True to enable the aggregation view." |
| `time.on_history_reset` | `warn` | Policy for history-affecting schema changes detected at history-load time. `warn` logs a WARNING and continues; `error` raises `HistoryResetError` so a CI run can never silently lose a baseline; `ignore` logs at DEBUG only. Retained data is never deleted by any policy. |

`time.max_slider_points` matters more than it looks: the slider states are pre-computed and
baked into the saved HTML, so an unbounded history makes the report large. The default of
10 caps that cost, and the aggregated tab still sees every point.

Result variables also accept a per-variable `max_time_events=`, which ages that column out
independently of the benchmark-wide setting. For media result types the aged-out cell's
file is deleted with it.

## Feeding regression detection

Over-time history is what regression detection consumes: with `time.over_time=True` and
`regression.enabled=True`, bencher compares the latest run against the loaded history
after the merge and before writing the result cache. If regressions are found they are
logged as a warning and attached to the result as `regression_report`.

The method is chosen with `regression.method` (the other knobs below also live on the
`regression` sub-config, a `RegressionCfg`):

| Method | Threshold parameter | Behaviour (from the `regression.method` docstring) |
|---|---|---|
| `percentage` | `regression.percentage` (10.0) | "mean comparison vs historical mean" |
| `adaptive` (default) | `regression.mad` (3.5) + `regression.percentage` | "robust MAD-based step + drift test for noisy metrics" |
| `delta` | `regression.delta` | "absolute-unit change vs historical mean" |
| `absolute` | `regression.absolute` | "hard directional threshold, no history required" |

Direction comes from the result variable's `OptDir`, so a `minimize` metric regresses when
it grows and a `maximize` metric regresses when it shrinks. `regression.min_history` keeps
a young baseline from failing a run: a variable with fewer historical points than the
threshold still reports regressions, but they are marked `young_baseline` and never trigger
a failure. `regression.overrides` sets per-variable methods and thresholds — including a
bare number as shorthand for a hard `absolute` limit, and an empty dict to opt a variable
out entirely.

`absolute` is the one method that needs no history, so it fires from the very first
recording — useful as a hard budget alongside a trend check.

See the [Regression Detection gallery](reference/meta/regression/index) for one worked
example per method, and
[Machine-Readable Results](how_to_use_bencher.md#machine-readable-results-agents--ci) for
exporting the verdicts as JSON for a CI gate.

## Examples

| Gallery | Shows |
|---|---|
| [0 Float, Over Time](reference/meta/0_float/over_time/index) | Categorical-only sweeps tracked over time |
| [1 Float, Over Time](reference/meta/1_float/over_time/index) | The line-plot case the snippet above is taken from |
| [2 Float, Over Time](reference/meta/2_float/over_time/index) | Heatmaps with a time slider |
| [3 Float, Over Time](reference/meta/3_float/over_time/index) | The highest-dimensional over-time sweeps |
| [0 Float, Over Time + Repeated](reference/meta/0_float/over_time_repeats/index) | Repeats and time together |
| [Optimisation Over Time](reference/meta/optimization_over_time/index) | Optuna analysis across snapshots |
| [Time Event](reference/meta/advanced/example_advanced_time_event) | Labelling snapshots with an explicit event string |
| [Git Time Event](reference/meta/advanced/example_advanced_git_time_event) | Labelling snapshots by commit |
| [Max Time Events](reference/meta/advanced/example_advanced_max_time_events) | Trimming the oldest events |
| [Aggregation Over Time](reference/meta/advanced/example_advanced_agg_over_time) | Collapsing dimensions across snapshots |
| [Self Benchmark Over Time](reference/meta/performance/example_perf_self_benchmark_over_time) | Bencher tracking its own overhead |
| [ResultDataSet Over Time](reference/meta/result_types/result_dataset/example_result_dataset_1d_over_time) | Per-snapshot payload rendering |

## Appendix: known limitations

### The slider conflict across report tabs, and how it is worked around

When multiple `over_time` results (0D, 1D, 2D, 3D) are rendered in the same HTML report,
the slider widgets interfere with each other. Only one tab's slider actually updates its
plot; the others appear frozen.

**Root cause.** Panel's `save(embed=True)` pre-computes all widget states and bakes them
into the HTML as static JSON. When the document contains multiple `hv.HoloMap` objects:

- **Same `kdims` label** (e.g. all use `kdims=["over_time"]`): Panel merges them into a
  **single shared slider**. The slider only drives whichever HoloMap was last encountered
  during embedding; the other plots don't update.
- **Different `kdims` labels** (e.g. `"over_time_1D"`, `"over_time_2D"`): Panel creates
  separate sliders but computes the **Cartesian cross-product** of all widget values. With
  *k* sliders of *n* options each this produces *n^k* embedded states (exponential
  blowup). Worse, changing any one slider forces a global state switch that can break the
  others.

In short, Panel's embed mechanism cannot host multiple independent HoloMap sliders in a
single HTML document.

**Approaches tried:**

| Approach | Result |
|----------|--------|
| Make 1D line use explicit `hv.HoloMap` (same `kdims`) | Still one shared slider; last plot wins |
| Unique `kdims` names with same label | Panel ignores the name, uses the label — no change |
| Unique `kdims` labels | Cross-product explosion; only last slider works |
| Replace `hv.HoloMap` with `pn.bind` + `DiscreteSlider` | `pn.bind` doesn't embed states correctly for static HTML |
| `pn.pane.HoloViews(linked_axes=False)` | Embed skips the HoloViews pane entirely |

**The workaround in place.** Each report tab is saved to its own embedded HTML file, and a
lightweight index page provides tab buttons and an `<iframe>`. Each tab's HTML is a fully
independent document with its own widget namespace, so sliders never collide.

```text
index.html          <- tab buttons + iframe
_tabs/
  over_time_0D.html <- self-contained embedded page
  over_time_1D.html
  over_time_2D.html
  over_time_3D.html
```

This approach requires no changes to HoloViews or Panel internals, scales to any number of
tabs without cross-product blowup, and preserves the existing slider UX within each tab.

The line and curve result classes were also updated to use explicit `hv.HoloMap`
construction for `over_time` (matching the pattern already used by heatmap and bar). This
prevents hvplot's implicit `groupby` widget from being used, which could conflict with
explicit HoloMap sliders within the same tab. With the iframe isolation these changes may
not be strictly necessary, but they make the rendering more consistent across plot types.

### Embedded slider cost

Because every slider state is pre-computed at save time, report size grows with the number
of time points. `time.max_slider_points` (default 10) is the knob that bounds it; raise it
deliberately and check the resulting HTML size.

## See also

- [Feature Guide](intro.md) — the over-time feature in the context of the rest of bencher
- [Caching](caching.md) — the history cache and why `cache.clear` matters in a snapshot loop
- [Getting Started](how_to_use_bencher.md) — run configuration reference
