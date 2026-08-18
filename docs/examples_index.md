# Examples Index

Bencher's examples come in two flavours. The **generated gallery** covers the combinatorial
space — every plot type, every result type, every sweep shape — and is rebuilt by
`pixi run generate-docs`; browse it in the [Gallery Overview](reference/meta/gallery). The
**hand-written examples** below live directly in `bencher/example/` and exist because each
one demonstrates something the generator cannot: a real image pipeline, a crash-and-resume
story, a multi-stage workflow.

Run any of them with `pixi run python bencher/example/<file>.py`.

## Start here

| File | What it shows |
|---|---|
| [`example_simple_float.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_simple_float.py) | The minimal benchmark: one `FloatSweep` input, one `ResultFloat` output, `plot_sweep()` with no arguments. The shape every other example is a variation on. |
| [`example_levels.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_levels.py) | Sweeps `float_vars` against `subsampling_divisions` (via the `BenchMeta` self-describing benchmark) to show how sampling density trades against cost, and how higher divisions reuse the samples of lower ones. |
| [`example_workflow.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_workflow.py) | A 3D volume sweep with four objectives and explicit `OptDir` directions, run as a 2D and then a 3D sweep — the multi-stage optimisation workflow pattern. |

## Result types and media

| File | What it shows |
|---|---|
| [`example_image.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_image.py) | Renders a polygon to a PNG per sample with PIL and returns the path as a `ResultImage`, alongside numeric `area`/`side_length` results. Progressively adds sweep dimensions and appends `to_panes()` for each, and disables `cache_results` because the results are file paths. |
| [`example_video.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_video.py) | Simulates a Turing reaction-diffusion pattern, accumulates frames through `bn.VideoWriter()`, and returns the written file as a `ResultVideo`. `example_video_tap` additionally builds a `to_video_grid()` view. |
| [`example_rerun.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_rerun.py) | Samples a 1D float variable and captures a [Rerun](https://rerun.io/) recording per sweep point. |
| [`example_rerun2.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_rerun2.py) | Two paths for an `.rrd` file: view it locally via `rrd_to_pane`, or publish it to a git branch for sharing. |
| [`example_rerun_over_time.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_rerun_over_time.py) | A support module rather than a runnable example: a second-order control system whose step response is logged to a Rerun recording, plus peak-overshoot and settling-time metrics. Used by the generated Rerun and regression examples. |
| [`example_container_tabs.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_container_tabs.py) | The `PaneLayout` options — `grid`, `tabs`, `tabs_and_grid` — for arranging multi-dimensional container results. |
| [`example_tab_bar_sweep.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_tab_bar_sweep.py) | Sweeps the tab count and renders the resulting tab bar as an image, to see how it wraps under fixed styling. A UI regression benchmark of bencher's own report chrome. |

## Caching and execution

| File | What it shows |
|---|---|
| [`example_sample_cache.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_sample_cache.py) | `cache_samples` as crash insurance: the worker raises partway through, and a second run reloads the samples that did complete and finishes the rest. See [Caching](caching.md). |
| [`example_sample_cache_context.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_sample_cache_context.py) | Asserts exact worker/cache call counts across runs and tags, including `only_hash_tag`. The precise specification of when a sample is served from the cache. |
| [`example_collect_render.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_collect_render.py) | The collect/render split: `Bench.collect()` runs the sweep without constructing any plotting objects, `bn.save_result()` persists it, and `bn.render_report()` builds the HTML — safely from a separate process. |

## Configuration sources

| File | What it shows |
|---|---|
| [`yaml_sweep_list.py`](https://github.com/blooop/bencher/blob/main/bencher/example/yaml_sweep_list.py) | `bn.YamlSweep` over a YAML file of workload lists, aggregated into one metric per entry. |
| [`yaml_sweep_dict.py`](https://github.com/blooop/bencher/blob/main/bencher/example/yaml_sweep_dict.py) | `bn.YamlSweep` over YAML dictionaries, summarising each configuration into totals plus a `ResultContainer` holding the config itself. |

## Reporting and self-measurement

| File | What it shows |
|---|---|
| [`example_scorecard.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_scorecard.py) | The benchmark health scorecard. Fabricates benchmark summaries with hand-shaped over-time distributions rather than running real sweeps, so every rendering path (sparklines, verdict colours, std bands, category grouping) and every `ScorecardConfig` option can be evaluated. See [Scorecard](scorecard.md). |
| [`example_self_benchmark.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_self_benchmark.py) | Bencher benchmarking itself: sweeps problem size against a near-zero-cost worker and measures the framework's own per-phase timing, so overhead scaling is visible. `example_self_benchmark_over_time` accumulates that across commits. |

## Runners and aggregate entry points

| File | What it shows |
|---|---|
| [`example_benchrunner.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_benchrunner.py) | `bn.BenchRunner` with a run tag and progressive execution — `repeats`/`subsampling_divisions` as starting values, `max_repeats`/`max_subsampling_divisions` as ceilings. |
| [`example_all.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_all.py) | Adds several examples to one `BenchRunner` and runs them grouped into a single report. |
| [`example_docs.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_docs.py) | The image and video examples run together through a `BenchRunner` for documentation output. |

## Support modules

These sit in the same directory but are imported rather than run:

| File | Role |
|---|---|
| [`benchmark_data.py`](https://github.com/blooop/bencher/blob/main/bencher/example/benchmark_data.py) | Shared sweep configuration classes (`ExampleBenchCfg`, `AllSweepVars`, `SimpleBenchClass`, the `PostprocessFn`/`NoiseDistribution` enums) used across examples and tests. `AllSweepVars` in particular exercises every sweep type for serialization and hashing coverage. |
| [`example_utils.py`](https://github.com/blooop/bencher/blob/main/bencher/example/example_utils.py) | `resolve_example_path()`, which locates example assets whether the code runs as a script, a notebook, or an installed package. |

## Subdirectories

- `bencher/example/optuna/` — optimisation examples: `example_optuna.py` (a Rastrigin
  toy problem), `example_optimize.py` (the first-class `bench.optimize()` API and the
  `to_optimize()` one-liner), and `example_optimize_aggregate.py` (optimising a metric
  aggregated over a nuisance dimension).
- `bencher/example/generated/` — the auto-generated gallery. Do not edit by hand; it is
  produced by `bencher/example/meta/generate_examples.py`.
- `bencher/example/meta/` — the generators themselves, plus `BenchMeta`, the
  self-describing benchmark that `example_levels.py` sweeps.
- `bencher/example/experimental/` and `bencher/example/shelved/` — work in progress and
  retired examples; not part of the documented surface.

## Generated galleries by category

| Gallery | Covers |
|---|---|
| [0 Float Inputs](reference/meta/0_float_inputs/index) | Categorical-only sweeps, with and without repeats and over-time |
| [1 Float Input](reference/meta/1_float_input/index) | One float plus 0–3 categorical dimensions |
| [2 Float Inputs](reference/meta/2_float_inputs/index) | Two floats — the heatmap and surface cases |
| [3 Float Inputs](reference/meta/3_float_inputs/index) | Three floats — volume plots |
| [Optimisation](reference/meta/optimisation/index) | Optuna integration: basic, over time, and aggregated |
| [Result Types](reference/meta/result_types/index) | One example per result type across input dimensions |
| [Plot Types](reference/meta/plot_types/index) | Every supported plot type |
| [Bool Plot Types](reference/meta/bool_plot_types/index) | Plot types specialised for boolean results |
| [Subsampling Divisions System](reference/meta/levels/index) | Sampling density as a single knob |
| [Sampling Strategies](reference/meta/sampling/index) | Custom values, levels, uniform, int vs float |
| [Composable Containers](reference/meta/composable_containers/index) | Combining results with composition strategies |
| [Container Tab Layouts](reference/meta/container_tabs/index) | `PaneLayout` variants |
| [Aggregation](reference/meta/aggregation/index) | Collapsing dimensions with `aggregate` / `agg_fn` |
| [Constant Variables](reference/meta/const_vars/index) | Pinning parameters with `const_vars` |
| [Statistics](reference/meta/statistics/index) | Error bands, distributions, repeat-count comparisons |
| [Workflows](reference/meta/workflows/index) | Entry-point conventions, multi-sweep and BenchRunner patterns |
| [YAML Sweeps](reference/meta/yaml/index) | Sweeping over YAML-defined configurations |
| [Cartesian Animation](reference/meta/cartesian_animation/index) | An animated build-up of the Cartesian product |
| [Advanced Patterns](reference/meta/advanced/index) | Time events, cache patterns, shared axes, report saving |
| [Regression Detection](reference/meta/regression/index) | One example per `regression_method` |
| [Performance](reference/meta/performance/index) | Bencher's own overhead |
| [Publishing](reference/meta/publishing/index) | Publishing reports |
| [Rerun Integration](reference/meta/rerun/index) | Rerun recordings as results |
