# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **Intra-sample chart gallery examples now declare their container** rather than appending
  a report-level plot. `res.to(XYCurveResult, ...)` and friends *add* a plot below whatever
  `plot_sweep` already rendered, which for a `ResultDataSet` with no declared container is
  the raw table — so the example showed the rows and the chart. Declaring
  `container=bn.xy_curve(...)` puts the chart in the result's own position instead, which is
  what `example_plot_xy_scatter` already did. Affects `example_plot_xy_curve`,
  `example_plot_xy_histogram` and `example_plot_xy_hexbin`; the chart-type route is
  unchanged and still covered by tests.
- **`DataSetResult` now renders `ResultDataSet` results only.** It previously claimed every
  pane-type result, which made `bench.add(bn.DataSetResult)` / `plot_list=["dataset"]` a
  second name for the `panes` view on a sweep with no stored payload. Now that
  `ResultDataSet` is a generic payload store, a `container=` written for a payload must not
  be handed an unrelated result's value, so the view returns `None` for such a sweep instead
  of falling back. Use the `panes` view (`res.to_panes()`, or the default report) for
  image/video/string/reference results — it is unchanged, and both views share one render
  path (`BenchResultBase.map_sample_panes`).
- **Logging now goes through per-module loggers.** Every module logs via
  `logging.getLogger(__name__)` instead of calling `logging.info()` and friends on the
  root logger, so bencher's output can be configured and filtered per module (e.g.
  `logging.getLogger("bencher.job").setLevel(logging.DEBUG)`) without touching root.
  Records now carry their originating `bencher.*` logger name; anything that filtered
  bencher output by root-handler side effects should key off the logger name instead.
- **Dev toolchain: ruff 0.16.** Bumped the ruff pin to `<=0.16.0` (and the ruff-format
  prek hook to `v0.16.0`), which expands ruff's default rule set from `E4/E7/E9/F` to
  roughly 413 rules. Lint debt surfaced by the wider defaults is fixed; `DTZ001`/`DTZ005`
  (naive datetimes) and `RUF023` (unsorted `__slots__`) are ignored in `ruff.toml` with
  rationale — the `over_time` axis is a timezone-naive `datetime64` coordinate, and
  `__slots__` order feeds `hash_persistent()`. The formatter is scoped away from markdown,
  which 0.16 newly formats. Example generation now runs `ruff check --fix-only` alongside
  `ruff format`, so regenerated examples stay lint-clean. No runtime behavior change.

### Fixed
- **`hover=False` on an intra-sample chart now actually disables hover.** `set_default_opts`
  registers `tools=["hover"]` as a global holoviews default for most element types, so a
  spec that merely omitted the key got hover back and the option was a silent no-op.
  `tools` is now set in both directions (`[]` when off). Passing `tools=` through `**opts`
  still wins, as it is applied last.
- **A `ResultDataSet` renders on every run, not only the first.** With `over_time` and
  more than one event in the history, a stored payload reached `ds_to_container` with
  `over_time` still a live dimension: `_to_panes_da` drops `over_time` from the pane
  recursion so hvplot can use groupby, and the branch that rebuilds it for pane-type
  results only covered `ResultVideo`/`ResultImage`/`ResultRerun`. The render then died in
  `zero_dim_da_to_val` with `ValueError: Dimension over_time already exists` (no input
  vars) or, once another dimension was consumed first, in the `dataset_list` lookup with
  `TypeError: only integer scalar arrays can be converted to a scalar index` — one cause,
  two signatures, and via `to_auto` the traceback was swallowed and the plot silently
  vanished from the report. A `ResultDataSet` now renders the current event: its cells
  hold indices into `dataset_list`, which is rebuilt from the samples of the run doing the
  rendering, so the indices merged in from history address *this* run's list and a slider
  across the events would show the current payload under every past run's label. Scalar
  results keep their full `over_time` series. Two supporting hardenings: a length-1
  dimension on a point now collapses to a value instead of a one-element array, and
  `ds_to_container` names the result variable and the dimension that was not reduced
  rather than indexing a list with an array several frames later.

### Added
- **`xy_histogram` chart type** — bins one or more measured columns of a `ResultDataSet`,
  showing the distribution a single sample measured. Distinct from the existing
  `histogram`, which bins a `ResultFloat` across the sweep and so shows the spread of the
  repeats. `column=` takes a list to overlay several distributions, binned over a *shared*
  range so they are actually comparable, and drawn translucent so the one underneath stays
  readable; it defaults to every numeric column. `density=True` normalises instead of
  counting, and the y axis is labelled accordingly. An empty or all-NaN column produces
  empty bins rather than raising — numpy cannot pick a range for an empty array, and NaN is
  how bencher marks a sample missing, so NaN rows are dropped rather than poisoning the
  range. Gallery example: `example_plot_xy_histogram`.
- **`xy_hexbin` chart type** — the density counterpart to `xy_scatter`, taking the same
  axes and binning them into hexagonal tiles. For a cloud of tens of thousands of points
  the markers saturate and where the mass actually is becomes the thing a scatter cannot
  show. `gridsize=` sets the resolution, `min_count=1` drops empty tiles, and the colourbar
  is on by default since a density plot without one shows shape but no magnitude. Gallery
  example: `example_plot_xy_hexbin`.
- **`hv.HexTiles` now carries the shared default figure size.** It was absent from
  `HoloviewResult.DEFAULT_SIZED_ELEMENTS`, so a hexbin would have fallen back to the
  holoviews default rather than bencher's 600x600 — the same gap Histogram/Area/ErrorBars
  were fixed for previously.
- **`xy_curve` chart type** — draws one or more *measured* columns of a `ResultDataSet`
  against an x column, for a benchmark that collects a whole series as one sample. The
  gap it fills: `curve` and `line` plot *across* the sweep, with one value per sample, so
  they cannot show a series that lives inside one. Available the same two ways as
  `xy_scatter`: `bn.xy_curve(x="time", y="signal")` returns a picklable spec usable as a
  `ResultDataSet(container=...)`, and `XYCurveResult` is registered as a **named-only**
  chart type. `y=` takes a list to overlay several series with a legend, `markers=True`
  adds a marker per row for a sparse series, and `sort=False` keeps the frame's row order
  so a trajectory that doubles back in x is drawn as travelled rather than sorted into a
  function of x. Gallery example: `example_plot_xy_curve`.
- **A named DataFrame index is now plottable as a column.** `Dataset.to_pandas()` — the
  idiomatic way to build a `ResultDataSet` from xarray — leaves the dimension coordinate
  in the index and only the data variables in the columns, so the x axis was unreachable
  by any chart and inference saw a single-column frame. `to_dataframe` now promotes named
  index levels to columns, at the front so inference finds the x axis first. An unnamed
  `RangeIndex` is row position rather than data and is left alone; a level whose name is
  already a column keeps its values and loses its name, since pandas rejects a label that
  is both an index level and a column as ambiguous. The `ResultDataSet` gallery examples
  (`example_result_dataset_1d`/`_2d`) and `BenchableDataSetResult` now declare an
  `xy_curve` container, so they show the collected series as a curve rather than as a
  table of raw rows.
- **Generic per-sample data rendering, with tabular handling kept at the edge.**
  `BenchResultBase.map_sample_panes` is the single operation that retrieves each stored
  sample and optionally maps a renderer over it; it neither checks nor converts the payload
  type, and takes the result types it claims as a parameter. Both per-sample views now go
  through it — `PaneResult.to_panes` (every pane type, and the path the default report
  takes) and `render_data_samples` (`ResultDataSet` only) — so a fix to the render path
  reaches the report and the chart types alike. `XYScatterResult` composes
  `render_data_samples` instead of introducing a parallel result hierarchy. The opt-in
  `holoview_results/tabular_spec.py` module only contains renderer-side concerns:
  `TabularSpec`, a frozen (therefore picklable) dataclass whose `__call__` coerces
  supported table-like data to a DataFrame, shared HoloViews options, and column helpers
  (`to_dataframe`, `check_column`, `resolve_axes`, `plot_frame`, `value_columns`).
  `TabularSpec` is exported as `bn.TabularSpec`, since writing a new chart type is what it
  is for. Column-validation errors name the chart that rejected the column, for every
  column a chart plots — including the ones a chart *option* implies (`color=`), which
  `value_columns` validates rather than letting them reach pandas as a bare `KeyError`.
  Chart types keep
  naming their options explicitly rather than accepting `**kwargs`: `**kwargs` belongs
  to `map_plot_panes`, and a signature-based split could not tell a pane-sizing `width`
  from a HoloViews style `width`.
- **`xy_scatter` chart type** — scatters two *measured* columns of a `ResultDataSet`
  against each other, for results whose rows are the measurement (landing points, hit
  locations, a phase-space cloud). Distinct from the existing `scatter`, which puts an
  input variable on x and a result variable on y; here both axes come from inside one
  sample and the sweep dimensions separate one plot from the next. Available two ways
  from one implementation: `bn.xy_scatter(x=..., y=..., color=..., data_aspect=1)`
  returns a picklable spec usable as a `ResultDataSet(container=...)`, so the cloud
  renders in `result_vars` order with the other results; and `XYScatterResult` is
  registered as a **named-only** chart type (`bench.add(bn.XYScatterResult, x=..., y=...)`
  or `to_auto(plot_list=["xy_scatter"], ...)`), so no existing report gains a plot it
  did not ask for. Columns are validated against the frame — a typo names the available
  columns instead of rendering nothing — x/y are inferred from the numeric columns when
  omitted, `data_aspect=1` gives the equal-aspect scaling a position cloud needs, and
  DataFrame / xarray / `hv.Dataset` objects are all accepted. The
  `example_plot_xy_scatter` gallery declares this renderer on its result, so the default
  report contains the scatter in place of the raw table rather than appending both.
- **`ResultDataSet(container=...)`** — `ResultDataSet` is a generic per-sample store for
  any picklable Python payload, with no DataFrame/xarray requirement. It can declare how
  the payload renders, the way `ResultReference` already could. The callback takes the
  stored object and returns anything Panel can display, so domain data shows up as the
  view it means, *in `result_vars` order* with the rest of the results.
  Precedence: a container passed to a renderer wins, then one attached to the stored
  sample (`ResultDataSet(data, container=...)` inside `benchmark()`), then the one declared
  on the class. The callback is invoked with the object alone (no plot kwargs), so
  single-argument callables are safe. An explicit
  `bench.add(bn.DataSetResult, container=...)` view still appends to the end of the report
  and cannot sit among the other result variables. `container` is in
  `_hash_exclude`, so declaring one does not change any cache key. A declared container
  rides in `BenchCfg` into the result cache and the collect/render split, so it must be
  picklable — a module-level function or a callable object, not a lambda.
- **Plot-selection signature enrichment** (A2 Phase S1): `PltCntCfg` gains additive, cheaply-computed facts alongside the existing counts — `has_time`/`time_steps` (temporal axis presence and length), `result_kinds` (result-variable name → coarse serializable kind, via the new `result_kind` / `RESULT_KIND_ORDER` in `bencher.variables.results`), `cat_levels` (levels per categorical input), and `samples_per_point` (min repeat count actually present at the latest time step, missing-sentinel-aware per result type, vs the configured `repeats`). `generate_plt_cnt_cfg` takes an optional dataset for the data-derived facts, `PltCntCfg.__str__` includes the new fields, and the aggregation plotting path carries them through. No selection behavior changes.

## [1.116.0] - 2026-07-11

### Changed — cache-busting release (`CACHE_VERSION` 4 → 5)

Every benchmark-level and `over_time` history cache key changes in this
release: expect a one-time cache miss and a fresh history series per the
standing cache policy (no migration of old entries). Implements plans 09 and
14 (`plans/09-result-cache-invalidation.md`,
`plans/14-history-schema-reconciliation.md`).

- **`BenchCfg.hash_persistent` composition** (plan 09):
  - `result_vars` and `const_vars` now contribute as an *unordered set* —
    reordering either no longer resets caches or history (D1).
  - Every per-variable identity (input, result, const) now includes the
    variable's **name** — renaming a variable is a detected identity change
    instead of a silent history split or phantom-dimension broadcast (D2).
- **`over_time` history survives result-variable changes** (plan 14): the
  history cache is keyed *without* result vars
  (`hash_persistent(True, include_result_vars=False)`) and stores a superset
  record of every column ever measured. At load time, columns are reconciled
  per identity `(name, class, units, meaning_version)` — added columns are
  NaN-backfilled and birth-stamped, removed columns go dormant (retained,
  invisible, resumed on return), redefined columns are retired under a mangled
  name and restart — and consumers receive a projection onto exactly the
  current config's columns. The benchmark-level result cache stays strict.

### Added

- **`meaning_version`** on `ResultFloat`/`ResultBool` — bump it when a metric
  keeps its name but changes meaning; that column's history and regression
  baseline restart cleanly while every other column continues.
- **`BenchRunCfg.on_history_reset`** (`"warn"` default / `"error"` /
  `"ignore"`) — loss-y history events (full reset with a named diff and
  orphaned-event count via a per-benchmark last-seen index, column dormant,
  column retired, incompatible history discarded) are logged, raised
  (`bencher.HistoryResetError`, before any state is persisted), or suppressed.
  Pre-record (bare-dataset) history entries participate in the same lifecycle:
  a column they carry that leaves the config is reported dormant, and it
  resumes rather than restarts when it returns.
- **`BenchRunCfg.regression_min_history`** (default 1 = previous behavior) —
  regressions on a baseline younger than N points since the column's birth are
  reported and exported (`young_baseline: true` in `result.json`,
  `RegressionReport.has_blocking_regressions`) but never trigger
  `regression_fail`; history-free `absolute` checks still gate. Per-variable
  override via a `min_history` key in `regression_overrides`. Young rows are
  marked notify-only (†) in the rendered regression report, the scorecard
  shows them as uncolored trend cells, and the exported report JSON carries a
  top-level `has_blocking_regressions`.

## [1.115.0] - 2026-07-11

### Added
- **`BenchResult.explain_selection()` / `PluginRegistry.explain()`** (A2 Phase S2): the full plot-selection decision table — one row per registered plugin, chosen entries first, each rejected entry carrying the first gate that dropped it (named-only, not in `plot_list`, excluded, missing capability, shape-filter mismatch, superseded backend resolution). `select()` is now exactly the chosen subset of `explain()`, so the table is the authoritative record of why a plot did or did not appear.
- **Scorecard orientation toggle** — each category's table can now be read two ways, switched by a control in the page header (the choice persists via `localStorage`). The default *metric across benchmarks* view is unchanged (one column per metric, one row per benchmark); the new *metrics within benchmark* view transposes it (one column per benchmark, one row per metric) so a benchmark's metrics stack with their sparkline time axes aligned. Both orientations are rendered from a single set of per-benchmark cells through one shared cell macro; the switch is pure show/hide of the pre-rendered tables, so it needs no data round-trip.

## [1.114.0] - 2026-07-06

### Added
- **Every result type is now addressable by name in `to_auto`** (A1 Phase 3). New *named-only* plugin concept: plugins with `auto=False` never appear in automatic selection but are selected when explicitly named via `plot_list`/`include`/`only` (`@bencher.plot_plugin(..., auto=False)`; the attribute is optional on the `PlotPlugin` protocol, read with a `getattr` default, so existing plugins are unaffected). The non-default built-ins register this way: `violin`, `scatter_jitter`, `scatter`, `band`, `table` (holoviews); `tabulator`, `dataset`, `video_summary` (panel); `surface` (plotly — only where a plot already required it, like `volume`); and `rerun` as its own first-class backend (the rerun SDK is imported lazily inside the renderer, so registration is safe without it installed). **Default report output is unchanged** (parity tests unaffected); e.g. `res.to_auto(plot_list=["violin"])` now works by name.
- `LegacyResultPlugin.render` filters the ride-along kwargs (`override`, plot size) to the callback's signature when the renderer has no `**kwargs` (e.g. `RerunResult.to_rerun`), instead of failing with a `TypeError`.
- `TableResult` and `TabulatorResult` joined `BenchResult`'s base list: named-only callbacks are unbound methods invoked on the live `BenchResult`, and `TabulatorResult.to_plot` (via `self.to_tabulator`) crashed with `AttributeError` without it.

## [1.113.1] - 2026-07-06

### Dependencies
- Bumped `rerun-sdk` and `rerun-notebook` upper bounds to `0.34.0`.
- Bumped upper bounds on `holoviews` (`1.23.1`), `numpy` (`2.5.1`), `scikit-learn` (`1.9.0`), and `matplotlib` (`3.11.0`).
- Bumped dev/test upper bounds on `hypothesis` (`6.156.1`), `coverage` (`7.15.0`), and `ty` (`0.0.56`).

## [1.113.0] - 2026-07-04

### Added
- **Benchmark health scorecard** (`bencher.scorecard`) — renders a set of benchmark result summaries into a single grouped HTML page where every scalar metric shows a regression verdict and a noise sparkline, so run-to-run trends are visible without opening each benchmark's full report.
  - `generate_scorecard(reports_dir, config, *, chrome, output_name)` walks `<reports_dir>/<layout.root>/<tag>/*.summary.json`, groups benchmarks by category, builds one row per benchmark and one column per (aliased) scalar metric, and writes the page. Benchmarks with only image reports are listed as plain links so they stay reachable.
  - Everything project-specific is injected via `ScorecardConfig`: the `tag -> (category, name, description)` registry, metric-name `aliases` (so equivalent metrics from different benchmarks share a column), `percent_metrics` (0..1 fractions shown as percentages), and the on-disk `ReportLayout`. Every field defaults, so the zero-config path still renders. Optional `Chrome` supplies page title, provenance, and CI nav links.
  - Cell verdicts reuse the core 3-state regression verdict and add a presentation-level split: a gated metric that didn't move renders `passed`, an ungated metric renders `trend` (uncolored, with a self-computed latest-vs-previous delta). Each cell also shows the μ mean of its series.
- **`sparkline_svg(means, stds)`** (`bencher.sparkline`) — a responsive inline-SVG sparkline: a ±std noise band, a mean line, a node per run, and a right-margin distribution column (one alpha-blended dot per run collapsed onto the value axis, so run-to-run spread and bimodality the line hides read as density). Pure-numeric input (safe to embed unescaped); `preserveAspectRatio="none"` + non-scaling strokes let CSS stretch it to any width. Uncolored — the caller (e.g. a verdict-colored cell background) owns any color.
- **`result_to_dict(bench_res, *, include_series=True)`** (and `result_to_json`, plus the new public `series_for_var`) — attaches a per-time-event `mean`/`std`/`n` series to each scalar metric when the result carries an `over_time` axis. Off by default, so the base contract stays byte-stable; this is the trend the scorecard sparklines render.
- **Scorecard example + docs page** — `bencher.example.example_scorecard` fabricates benchmark summaries across distribution archetypes (stable, low/high noise, improving, regressing, ungated trend, step change, converging/expanding noise, outlier spike, first run) plus a config-options showcase (aliases, percent metrics, chrome), so the rendering can be evaluated in isolation. Rendered into the docs (`docs/scorecard.md`) with the live page embedded.

### Dependencies
- Added `jinja2` (already present transitively via panel/bokeh) — used to render the scorecard template shipped as package data.

## [1.112.0] - 2026-07-02

### Added
- **`BenchRunCfg.regression_overrides`** — per-variable regression specs. Maps result-variable name → a `{method: threshold}` dict drawn from `percentage` / `adaptive` / `delta` / `absolute`, or a bare number as shorthand for `{'absolute': value}` (a hard directional limit: minimize = ceiling, maximize = floor).
  - A listed variable is checked by exactly the methods in its spec **instead of** the benchmark-wide `regression_method`, so a threshold can be loosened *or* tightened per variable; an explicit `{}` opts a variable out of detection. Unlisted variables keep the benchmark-wide method, and names matching no result variable are skipped, so one override map can be shared across benchmarks.
  - Multiple entries run as independent checks — `{'percentage': 15.0, 'absolute': 1.0}` tracks the trend and holds a hard floor. `absolute` checks need no history and fire from the very first recording; the other methods skip until history exists.
  - Adaptive overrides: the threshold is the MAD limit (the dual-band percent gate still comes from `regression_percentage`); while history is too sparse for MAD the check skips instead of falling back to a percentage check, so a listed variable is never judged by a knob outside its spec.
  - Malformed specs never crash a run: unknown method keys and non-finite/bool thresholds are dropped with a warning, and a spec left with no valid checks keeps the benchmark-wide method (a typo can't silently disable detection). Bare-number shorthand accepts numpy scalars.
  - Motivating use case: CI tracking of flat health metrics (a success rate that must hold 1.0, an orphan-process count that must hold 0) next to per-metric trend thresholds on the same benchmark. Breaches flow through the existing machinery unchanged (`has_regressions`, `regression_fail`/`RegressionError`, report markdown, JSON, `render_png`).
  - First mutable (`param.Dict`) field on `BenchRunCfg`: every `BenchRunner` copy point deepcopies and the default is `None`; recorded in the copy-guard test's `REVIEWED_MUTABLE_FIELDS` allowlist with nested-dict isolation tests.

### Changed
- `detect_absolute` with `OptDir.none` now warns and returns `None` instead of recording a non-regressed "checked" result — a guard with no direction never ran, so it no longer appears to have passed.

## [1.111.0] - 2026-07-01

### Changed
- **`to_auto` dispatches through the plot plugin registry** (A1 Phase 2). The built-in chart types (bar, box_whisker, curve, line, heatmap, histogram, volume, panes) are registered as thin wrappers (`bencher/plugins/builtins.py`) that delegate to the existing renderer methods — renderer logic and report output are unchanged (priorities encode the legacy callback order; parity covered in `test/test_plugins_builtins.py`). What changes: user plugins registered with `@bencher.plot_plugin` / `bencher.register_plugin` or shipped via the `bencher.plot_plugins` entry-point group now appear in reports automatically; built-ins can be overridden by registering the same (name, backend); `plot_list`/`remove_plots` accept plugin names (`"line"`, `"heatmap"`, ...) alongside the legacy callables (which keep working, unknown callables via direct call); and `to_auto(backend=...)` states a preferred rendering backend — chart types the preferred backend implements swap to it, the rest keep their best other implementation.
- New `BenchResult.to_bench_data()` builds the frozen `BenchData` contract from a live result (first step of the A3 data-contract migration). Transitional `BenchData.legacy_result`/`render_kwargs` fields carry the live result and plot kwargs for the wrapped built-ins; they are not part of the stable plugin contract and disappear when renderers consume `BenchData` directly.

## [1.110.0] - 2026-07-01

### Added
- **Plot plugin infrastructure (tier 0, purely additive)** — the first piece of the plan to replace the inheritance-based rendering system in `bencher/results/` with a plugin registry (see `plans/architecture/A1-rendering-backend-unification.md` and `docs/plot_plugin_design.md`). New `bencher.plugins` package exposing, at the top level: `BenchData` (frozen value type: dataset, input/result vars, `plt_cnt_cfg`, `RunMeta`, optional `optimizer_study`/`baseline_runs`/`cache`), the `PlotPlugin` protocol and `@plot_plugin` decorator, and `PluginRegistry` with `get_registry()`/`register_plugin()`/`unregister_plugin()`. Plugins are `(chart-type × backend)` pairs with a `PlotFilter` match rule, priority, capability gating via `requires`, lazy entry-point discovery (`bencher.plot_plugins` group), and error-pane substitution on render failure (`strict=True` re-raises). **No existing code path queries the registry yet**; built-in chart types migrate onto it in subsequent PRs. Coverage in `test/test_plugins.py`.

## [1.108.0] - 2026-06-21

### Added
- `bencher` console-script entry point (`[project.scripts]` → `bencher.render:main`), so the render/compare CLI can be invoked as `bencher <result.pkl> <out_dir> [--json PATH]` and `bencher compare <a.pkl> <b.pkl> --json PATH` instead of only `python -m bencher.render …`. **Non-breaking**: the existing `python -m bencher.render` invocation is unchanged and keeps working; this is purely an additional way to reach the same `main()`. Usage/`--help` text is now invocation-aware via a small `_prog()` helper — it shows `bencher` under the console script and `python -m bencher.render` from a source checkout — so the displayed command always matches how the tool was run. Coverage in `test/test_render.py`.

## [1.107.0] - 2026-06-12

### Changed
- Centralised the representation of *missing*/unrecorded result-variable entries. The dtype-specific sentinels (`NaN` for numeric types, `-1` for `ResultReference`/`ResultDataSet`, `"NAN"` for object/file types) were duplicated across `ResultCollector.setup_dataset` (initial fill) and `_sentinel_for_result_var` (over_time aging), and consumers hardcoded the check per call site (`== "NAN"` for file panes). New helpers in `bencher.variables.results` — `result_missing_fill(rv)` and `result_is_missing(rv, value)` — are now the single source of truth; the two `isinstance` ladders collapse into one polymorphic call and the hardcoded `== "NAN"` file checks in `bench_result_base.py` use the shared predicate. **No behaviour change**: the stored fill values and dtypes are identical, so the on-disk cache format, `BenchCfg` hashes, and every reduction are unchanged (`CACHE_VERSION` stays at `4`). Direct coverage in `test/test_result_missing.py`.

## [1.106.2] - 2026-06-12

### Added
- `catch` parameter on `Bench.optimize()`, forwarded to `optuna.Study.optimize()`: a trial whose worker raises one of the given exception types is recorded as `FAILED` and the study continues with the remaining trials, instead of one raising trial aborting the entire study. The default `()` mirrors Optuna's own default and preserves the existing fail-fast behaviour exactly. `ParametrizedSweep.to_optimize()` already forwards `**kwargs`, so it picks up `catch` with no change. A raising worker leaves no committed sample-cache entry (both the serial and parallel paths raise before `cache.set`), so `FAILED` trials cannot poison the cache. Coverage in `test/test_optimize.py::TestCatch`.

## [1.106.1] - 2026-06-12

### Changed
- Version-only re-release of 1.106.0; no code changes.

## [1.106.0] - 2026-06-12

### Fixed
- `Bench.optimize()` never passed `const_vars` to the worker: `_run_optuna_job` folded the constants into the **cache key** but submitted only the trial-suggested values as `job_args`, so every Optuna trial silently ran with the worker class's parameter *defaults* for all `const_vars`. Constants are now merged into the submitted `job_args` (mirroring the sweep path's `WorkerJob.setup_hashes`); trial-suggested values keep precedence since `_resolve_optimize_vars` already strips colliding const entries. Regression coverage in `test/test_optimize.py::TestConstVars` for both the plain and `aggregate`/`repeats>1` branches.
- `CACHE_VERSION` bumped to `"4"`: because the old cache key already included the constants, any cached `optimize()` entries produced with non-default `const_vars` hold values actually computed with worker defaults — wrong data under a correct-looking key, indistinguishable on disk from good entries. The bump wipes the cache tree on first use of the new version so the fixed code can never warm-start from poisoned entries.

## [1.105.0] - 2026-06-11

### Changed
- The default value for `ResultFloat`, `ResultVec`, and `ResultBool` is now `NaN` instead of `0`. An *unrecorded* sample — a run that aborts before measuring, or a result var the worker never sets — is now treated as missing and dropped by the nan-aware regression/aggregation reductions, instead of masquerading as a real `0`/`False` measurement and dragging means toward zero. This matches the storage layer, which already initialises result arrays with `NaN`. Callers who want unrecorded samples to read as `0` can opt out with `default=0`.
- For `ResultBool`, this means **missing ≠ failure**: an unrecorded repeat is dropped from the success proportion rather than counted as `False`. A worker that wants a crash/abort to count as a failure must explicitly record `False` on its failure path. The binomial standard error already divides by the per-cell count of valid (non-NaN) repeats (see 1.104.2), so missing repeats no longer understate the SE.
- `CACHE_VERSION` is **not** bumped: the result-var `default` is not part of `BenchCfg.hash_persistent()`, so existing benchmark and `over_time` history caches are preserved. The new `NaN` default only applies to cache *misses* (newly computed cells); already-cached cells keep whatever sentinel they were stored with, so a benchmark with missing samples may transiently hold a mix of `0` (old) and `NaN` (new) until those cells are recomputed.

## [1.104.2] - 2026-06-10

### Fixed
- `ResultBool` rejected NaN as a default or value even though NaN is the documented "missing"/unrecorded sentinel for result variables (see `ResultFloat.__init__`). `ResultBool` locks its bounds to `[0, 1]`, and param validates a Parameter's default against its bounds whenever a subclass *overrides* it (and validates every value assignment). So `ResultBool(default=float("nan"))` raised `must be at most 1, not nan` the moment a subclass overrode the inherited Parameter, and assigning `float("nan")` at runtime to mark a sample missing raised the same — making the NaN "missing" sentinel that already works for `ResultFloat` unusable for `ResultBool`. `ResultBool._validate_bounds` now treats NaN as in-bounds, so result bools can use the same missing sentinel as `ResultFloat` while genuinely out-of-range values (e.g. `2.0`) are still rejected. Added coverage in `test/test_result_nan_default.py`.
- The `ResultBool` binomial standard error (`REDUCE` path in `bench_result_base.py`) divided `p*(1-p)` by the full repeat-dimension size while computing `p` with a `skipna=True` mean. Now that NaN is a valid "missing" repeat for `ResultBool`, those diverged and the SE was understated whenever a repeat was missing. The SE now divides by the per-cell count of valid (non-NaN) repeats. Added coverage in `test/test_result_bool.py`.

## [1.104.1] - 2026-06-09

### Fixed
- 30° x-axis label rotation (and `title`/`ylabel`) were silently dropped on plots that hvplot returns as a panel layout — specifically over_time time-series lines that pair `widget_location="bottom"` with an extra categorical `by` widget, which come back as a `pn.Column([HoloViews pane, WidgetBox])`. `HoloviewResult._apply_opts` only handled bare HoloViews elements (`.opts`) and `pn.pane.HoloViews` wrappers (`.object`); the layout container has neither, so the options never reached the nested pane and long x-axis labels (e.g. `over_time` datetime/`TimeEvent` ticks) rendered horizontally and unreadable. `_apply_opts` now recurses into panel layout containers to apply options to the nested pane. hv elements never expose `.objects`, so the new branch only catches panel layouts. Added unit coverage in `test/test_holoview_result.py` for all three input shapes (bare element, pane wrapper, layout container).

## [1.104.0] - 2026-06-08

### Changed
- Sped up `import bencher` (~19s → ~4s warm) by lazy-loading two heavy plotting dependencies that were imported eagerly at module load but only needed when a plot is rendered. `holoview_result.py` no longer registers the holoviews plotly backend (`hv.extension("bokeh", "plotly")` → `hv.extension("bokeh")`) — nothing in bencher renders through it, since `SurfaceResult`/`VolumeResult` build `plotly.graph_objs` figures directly and wrap them in `pn.pane.Plotly`. The `optuna.visualization` imports (which pull in sklearn's fANOVA evaluator) were moved into the functions that use them (`param_importance()`, `collect_optuna_plots()`). No public API changes.

## [1.103.1] - 2026-06-08

### Fixed
- Histograms rendered at hvplot's default 700×300 instead of the shared 600×600 used by every other plot type. `HoloviewResult.set_default_opts()` registered the default figure size for `Curve`, `Points`, `Bars`, `Scatter`, `BoxWhisker`, `Violin`, and `HeatMap`, but `Histogram` was missing so it escaped to hvplot's own default. Also registered `Area` and `ErrorBars` for consistency (`ErrorBars` would likewise escape when returned standalone from `to_error_bar()`; `Area` previously inherited the size only by virtue of being overlaid). The default-sized element list is now centralized in `HoloviewResult.DEFAULT_SIZED_ELEMENTS` and reused by both `set_default_opts()` and `test_default_opts_cover_all_element_types`, so the coverage guard stays in sync as new element types are added.

## [1.102.0] - 2026-06-02

### Added
- Optional `default=` argument on `ResultFloat` and `ResultVec` (defaults to `0`, so no behaviour change). The hardcoded `0` default meant an *unrecorded* sample — a run that aborts before measuring, or a result var the worker never sets — was indistinguishable from a real `0` measurement, dragging nan-aware regression/aggregation means toward zero. Callers can now opt in with `default=float("nan")` so unrecorded samples are treated as missing and dropped by the existing `np.nanmean`/`np.nansum` reductions. `default` is not a hashed slot, so opting in does not invalidate `over_time` history for an otherwise-identical result var.
- `test/test_result_nan_default.py`: backward-compat (default still `0`), NaN/explicit-default opt-in, hash stability, end-to-end unrecorded-sample handling, plus serialization coverage — a pickle `save_result`/`load_result` round-trip and a HoloViews→bokeh `render_report` HTML render both preserve/handle the NaN default.

## [1.101.1] - 2026-06-01

### Fixed
- Pylint failures introduced by the `param` 2.4.0 / `panel` 1.9.2 dependency bumps: the deeper class hierarchy pushed several sweep classes (`BoolSweep`, `StringSweep`, `EnumSweep`, `YamlSweep`, `IntSweep`, time sweeps) over the `too-many-ancestors` threshold, so that check is now disabled alongside the other `too-many-*` checks.
- Renamed the `IntSweep._validate_value` parameter from `val` to `value` to match param 2.x's signature and silence `arguments-renamed` (W0237).

- Cleared the three pre-existing `ty` warnings: corrected the `_InputResult` namedtuple's first argument to match its variable name, explicitly imported `moviepy.video.VideoClip` for the `write_video_raw` annotation, and suppressed the `unsupported-base` false positive on `BenchResult`'s optional `RerunResult` base.

### Changed
- Raised the minimum `param` requirement from `>=1.13.0` to `>=2.0`. The validation override now matches param 2.x's `_validate_value(self, value, allow_None)` signature.
- Dependency audit: raised upper bounds to the latest releases — `numpy` `<=2.4.6`, `xarray` `<=2026.4.0`, `pandas` `<=3.0.3`, `scikit-learn` `<=1.8.0`. Full test suite passes against all bumped versions.
- Migrated panel widget construction from the deprecated `name=` to `label=` (`Button`, `DiscreteSlider`, and example sliders) ahead of its removal in panel 2.0, and raised the panel floor to `>=1.9.0` (the release that introduced `Widget.label`).

## [1.101.0] - 2026-06-01

### Added
- Collect/render split for out-of-process report rendering. Building a report allocates large holoviews/panel/bokeh object graphs; when CPython's cyclic GC traverses them alongside foreign live C-extension state (e.g. ROS 2 `rclpy`/DDS), the process can segfault. The split lets rendering happen in a clean process that never imported the foreign extension:
  - `plot_sweep(auto_plot=...)` — new parameter (defaults to `None`, deferring to `run_cfg.auto_plot`, itself `True`). When `False`, the sweep runs and regression detection is computed but no plotting objects are constructed.
  - `Bench.collect(...)` — thin wrapper for `plot_sweep(auto_plot=False)`; returns a fully-populated, picklable `BenchResult` (dataset + regression report).
  - `bencher.save_result()` / `load_result()` / `render_report()` (new `bencher.render` module) — persist a collected result and render the HTML report from it, optionally in a separate process via `python -m bencher.render <result> <out_dir>`.
- Three test layers guarding the split against divergence from the normal `plot_sweep` path: parity tests (`collect()` computes the same dataset/regression as `plot_sweep()`), a breadth round-trip over every generated result type (save → load → render to HTML, plus a real-subprocess media test), and the `BENCHER_FORCE_SPLIT_RENDER=1` switch that reroutes every auto-plot report build through serialize/render-from-loaded so `pixi run test-split` re-runs the whole suite over the split pipeline (own parallel py313-only `ci-split` job).

### Changed
- `BenchReport.append_result()` gained an optional `render_from=` argument so a caller can register one result for identity-based tab routing while building the tab pane from another (used by the forced-split path).

## [1.100.0] - 2026-05-15

### Added
- Overlay controls on each embedded rerun recording: a fullscreen button (⛶) that calls `iframe.requestFullscreen()` and an open-in-new-tab link (↗) that opens the same chromeless viewer in a new browser tab. Useful when comparing multiple recordings side-by-side and you want to expand one. Controls are positioned top-center to avoid the viewer's own corner UI.

## [1.99.0] - 2026-05-15

### Changed
- Renamed `level` API to `subsampling_divisions` across the entire public interface (`BenchRunCfg.subsampling_divisions`, `subsampling_divisions_to_samples()`, `with_subsampling_divisions()`, `SUBSAMPLING_DIVISIONS_SAMPLES`, `max_subsampling_divisions`, `select_subsampling_divisions()`).
- Added `UNSET` sentinel for default detection so that `run(subsampling_divisions=2, level=3)` correctly raises `TypeError`.
- Extracted shared `normalize_subsampling_divisions_kwargs()` helper to centralize deprecation logic.
- Bumped `rerun-sdk` and `rerun-notebook` from 0.31.3 to 0.32.0.
- Updated fallback rerun version in `utils_rrd.py` to 0.32.0.

### Deprecated
- `level`, `max_level`, `min_level` parameters — use `subsampling_divisions`, `max_subsampling_divisions` instead. Old names still work with `DeprecationWarning`.
- `LEVEL_SAMPLES` constant — use `SUBSAMPLING_DIVISIONS_SAMPLES`.
- `with_level()` function — use `with_subsampling_divisions()`.
- `level_to_samples()` method — use `subsampling_divisions_to_samples()`.
- `select_level()` function — use `select_subsampling_divisions()`.

## [1.98.0] - 2026-04-27

### Added
- `aggregate`, `agg_fn`, and `repeats` parameters for `optimize()`, matching the `plot_sweep()` API. Aggregated dimensions are looped inside the Optuna objective so the optimizer sees robust metrics (e.g. mean loss across seeds or repeated boolean outcomes).
- `AGG_FN_MAP` in `bencher/utils.py` — NaN-safe numpy aggregation functions for objective-level aggregation.
- Example `example_optimize_aggregate.py` demonstrating sweep-then-optimize with dimension aggregation and repeats.

### Fixed
- Missing `skipna=True` on `REDUCE` and `MINMAX` repeat aggregation in `bench_result_base.py`.
- `np.mean` → `np.nanmean` in `optuna_result.py` aggregation to match xarray's NaN-safe behavior.

## [1.97.0] - 2026-04-27

### Fixed
- `aggregate=True` no longer duplicates pane-type results (rerun, image, video). Pane results store file paths that cannot be numerically aggregated, so they now only render in the non-aggregated view.
- Line plotter crash when aggregating: `plt_cnt_cfg` still referenced collapsed dimensions, causing holoviews `DataError` on missing dimension names. Swapped to post-aggregation config during `map_plot_panes` calls.
- `remove_plots` no longer raises `ValueError` when combined with `numeric_only`.

### Changed
- Renamed `VideoResult` to `PaneResult` to reflect that it handles all pane types (rerun, image, video), not just video.

### Added
- Image and video aggregate examples (`example_result_image_aggregate`, `example_result_video_aggregate`) to exercise and demonstrate pane-result aggregation.
- `omega_n` sweep added to `ControlSystemSweep` for multi-input rerun testing.

## [1.94.0] - 2026-04-25

### Fixed
- Rerun viewer panes now work in saved HTML reports (`show="html"` / `ShowMode.HTML`). Previously the viewer failed because browsers block `fetch()` from `file://` origins. The `.rrd` data is now base64-encoded directly into the viewer HTML page and loaded via the rerun `open_channel()` / `send_rrd()` API, bypassing the fetch entirely.
- Multi-tab reports with rerun panes: tab files in `_tabs/` now correctly reference `../_rrd/` instead of `_rrd/`, fixing broken relative paths.

## [1.93.0] - 2026-04-25

### Added
- `ShowMode` StrEnum (`live`, `html`, `published`, `none`) exported from the top-level `bencher` package. `bn.run(show=bn.ShowMode.HTML)` gives autocomplete and typo detection while plain strings (`show="html"`) and booleans (`show=True`) keep working. The old `"static"` spelling is accepted as an alias for `ShowMode.HTML`.

### Changed
- The `show` parameter on `bn.run()`, `BenchRunner.run()`, `BenchRunner.show()`, and `BenchPlotSrvCfg` now accepts `ShowMode` in addition to `bool | str`.
- Renamed the `"static"` display mode to `"html"` (`"static"` remains supported via alias).

## [1.92.0] - 2026-04-22

### Added
- `show` parameter on `bn.run()`, `BenchRunner.run()`, and `BenchRunner.show()` now accepts string display modes in addition to `bool`: `"live"` (start Panel server, blocks — same as `True`), `"static"` (save an embedded HTML file and open in the browser, returns immediately), `"published"` (open the published URL — requires `publish=True`), and `"none"` (display nothing — same as `False`).
- Public `MethodCells` dataclass and `method_cells(result)` helper in `bencher.regression`, re-exported from the top-level `bencher` package. Downstream report builders can now call `method_cells(r)` to get pre-rendered, method-aware display strings (change, baseline, threshold, summary lead) for a `RegressionResult` and embed them in a custom layout — custom columns, non-markdown output, CI comments with status decoration, etc. — without reimplementing per-method dispatch (and drifting when new detection methods are added).

### Removed
- The private names `_MethodCells` / `_method_cells` are gone. Update callers to the public `MethodCells` / `method_cells`.

## [1.91.0] - 2026-04-22

### Added
- Regression report is now auto-embedded as a Markdown panel at the top of `to_auto_plots()` whenever `regression_report.has_regressions` is true. Previously only the per-variable overlay plots were injected, so absolute-method fires (which have no history/overlay) were silent in the report.

### Changed
- Regression report rendering (`RegressionReport.summary()` and `to_markdown()`) now dispatches per method so each row describes its actual gate:
  - `percentage`: threshold shown as `±T%`.
  - `adaptive`: threshold shown as `Tσ` (change remains in percent).
  - `delta`: Change column shows the raw Δ (not percent, since the gate is in absolute units); threshold rendered as `±T`.
  - `absolute`: Change and Baseline cells rendered as em-dash (no historical baseline); Threshold cell carries the direction-aware inequality (`≤ L` for `OptDir.minimize`, `≥ L` for `OptDir.maximize`). Summary line phrased as `current=X vs ceiling|floor=Y`.

### Fixed
- `RegressionResult.summary()` / `RegressionReport.to_markdown()` no longer render `+nan%` or mislabel the hard limit as `Baseline` for `regression_method="absolute"` results.

## [1.90.0] - 2026-04-22

### Added
- `sampling_context` parameter on `bn.run()`: an optional context manager that wraps only the sampling phase. Its `__exit__` is guaranteed to run before the Panel/Bokeh server starts, so external resources (DB pools, GPU handles, simulators) are released while nothing blocks. `save` and `publish` still execute inside the context. Defaults to `None` (fully backward-compatible).

## [1.89.0] - 2026-04-21

### Added
- Two new values for `BenchRunCfg.regression_method`: `"delta"` and `"absolute"`. Each selects a dedicated detector and its threshold comes from a new `BenchRunCfg` field:
  - `"delta"` uses `regression_delta`: largest acceptable absolute-unit change of the current run's mean from the mean of all historical per-time means, respecting the result variable's `OptDir`. Useful when a percent threshold obscures sensitivity at tiny baselines or when CI wants a flat unit ceiling on drift.
  - `"absolute"` uses `regression_absolute`: hard directional threshold (ceiling for `OptDir.minimize`, floor for `OptDir.maximize`) against the current run's mean. No history required — fires on the very first recording.
- `detect_delta()` and `detect_absolute()` public detectors in `bencher.regression`, mirroring the `detect_percentage` / `detect_adaptive` shape so they participate in the shared plot/report pipeline.
- `detect_regressions()` now runs with a single `over_time` point when `regression_method="absolute"`, so contractual limits can gate even the initial benchmark run.
- Gallery examples `example_regression_delta` and `example_regression_absolute` demonstrating the new methods.

### Changed
- Regression diagnostic plot: when the adaptive detector produces both a MAD band and a percent band, they are now merged into a single combined acceptance band (the union of both — matching the adaptive gate, which flags a regression only when both tests fail). Previously the plot layered two separately-coloured bands.

## [1.87.0] - 2026-04-19

### Added
- PNG/bokeh regression diagnostic plot via `render_regression_png` (matplotlib) and `build_regression_overlay` (holoviews/bokeh) sharing a single plot spec, so the same diagnostic can be posted as a PR-comment PNG or embedded in the HTML report. `RegressionResult` now stores history/current samples and their `over_time` coordinates so plots use real datetimes when available.
- HTML report auto-inserts the regression overlay per regressed variable; bare over_time line/band plots are suppressed for any variable with a regression overlay to avoid duplicate graphs.
- Categorical x-axis support in regression plots (e.g. `git_time_event` string labels like `"2024-06-15 abc1234d"`), surfaced via xticks overrides.
- Dotted connector from the last history point to the current marker in regression overlays so the jump that triggered a regression is visually obvious.
- `matplotlib` added as a dependency for PNG rendering.

### Fixed
- `over_time` bar plot crash on duplicate coord values (e.g. two runs at the same `git_time_event` string) that caused `HoloMap must only contain one type of object, not both Bars and DynamicMap`. Switched `_build_time_holomap` and `_pane_over_time_{slider,grid}` to positional `isel(over_time=idx)` and deduped identical coord values.
- Holoviews `UFuncNoLoopError` with `git_time_event` string x-axes by replacing `HSpan`/`HLine` with `Area`/`Curve` primitives that carry explicit x coords, so the regression band and baseline always render regardless of x dtype.
- Regression plot dtype mismatch between `hist_x` and `current_x` (e.g. datetime64 vs int64) that raised in holoviews' range computation; `current_x` now only replaces the extrapolated tick when its dtype matches the history.
- Single-datetime-point regression overlays now nudge the current marker forward by a small timedelta so it doesn't overlap the sole history point.

## [1.86.0] - 2026-04-19

### Changed
- `BenchRunCfg.regression_method` default changed from `"percentage"` to `"adaptive"`. The adaptive method (robust MAD-based step + drift test) is more resilient to noisy metrics and is a better default for most benchmarks. Users can still opt into `"percentage"`, `"iqr"`, or `"ttest"` explicitly.

## [1.85.1] - 2026-04-19

### Fixed
- Rerun regression over-time line plots crashing when an acceptance band was overlaid on a `widget_location`-wrapped hvplot (panel pane), by composing the band onto `plot.object` when the plot is a pane wrapper.

## [1.85.0] - 2026-04-18

### Fixed
- **Benchmark-level cache identity for reshaped sweeps**: `SweepBase.hash_persistent` previously hashed only `(units, samples)`, so reshaping a `FloatSweep`/`IntSweep`/`SweepSelector` (changing bounds, step, `sample_values`, or `objects`) silently left the benchmark-level cache and `over_time` history keyed by the old shape, returning stale coordinates. Fixed by introducing an explicit `_sweep_identity` whitelist (bounds, sample_values, step, objects) with a slot-coverage test that catches future "added a slot, forgot the hash" regressions.
- `CACHE_VERSION` bumped to `"3"` and folded directly into `BenchCfg.hash_persistent` so version bumps atomically invalidate every benchmark-level and over_time key.

### Changed
- `ResultFloat.direction` and `ResultRerun.width`/`height` moved to `_hash_exclude`: these are interpretive/cosmetic fields that should not invalidate history when changed.
- New `TestGoldenBenchCfgHash` regression pins byte-exact values for a canonical `BenchCfg`; any future change to what contributes to the hash fails CI loudly and forces a deliberate `CACHE_VERSION` bump.

## [1.84.0] - 2026-04-12

### Changed
- Decouple benchmark title from cache hash so renaming a title no longer invalidates cached results or loses over_time history

## [1.83.0] - 2026-04-12

### Fixed
- `.rrd` filename collision in saved reports by using subdirectory structure for rrd sidecar files (#909)
- Guard `rrd_file_to_pane` against None/empty file paths
- Start over_time film-strip labels from t=1 instead of t=0 (#907)
- Skip rerun over-time entries with no data instead of showing placeholder (#905, #906)

### Changed
- Track all generated examples and remove duplicate cartesian animation
- Gitignore `bencher/example/generated/` to stop dirty working tree

## [1.81.0] - 2026-04-08

### Added
- Per-variable `max_time_events` support for fine-grained control over rerun time-series density (#899)
- Regression markdown output for result reporting

### Changed
- Pinned rerun-sdk to 0.31.1 for stability
- Rewritten rerun examples with improved over_time handling and result rendering

### Fixed
- Histogram rendering fixes
- Rerun over_time slider crash (#900)
- Cache management: cleanup timing, gen_path collisions, error handling, and type annotations (#899)
- Accidental generated file deletion during cache cleanup

## [1.80.1] - 2026-04-06

### Fixed
- Recover gracefully from stale history cache entries after dependency upgrades (#898)

## [1.79.0] - 2026-04-05

### Added
- **Rerun visualization backend** with seamless backend switching between holoviews and rerun (#755)
- `ResultRerun` type for dedicated `.rrd` result handling (#882)
- `extra_panels` parameter in `to_auto_plots()` for composability (#846)
- `LEVEL_SAMPLES` constant and `BenchRunCfg.level_to_samples()` for transparent level-to-sample lookups (#834)
- `samples_per_var` parameter on `BenchRunCfg` — explicit sample count that overrides `level` (#834)
- Improved `BenchRunCfg` docstring with quick-start examples and level-to-samples table (#834)
- Mermaid architecture diagram in concepts docs (#852)

### Changed
- `cache_samples` is now opt-in, with auto-enable for progressive runs (#889)
- Refactored holoviews backend: unified tap logic, time HoloMaps, and filter usage (#754)
- All generated example filenames now prefixed with `example_` (#890)
- Improved error messages, result validation, and example modernization (#895)
- Improved validation, error messages, and onboarding docs (#887)

### Fixed
- Type hints and error handling for `extra_panels` (#896)
- Use random port instead of `port=0` to avoid `EADDRINUSE` on Linux 6.x (#894)
- Save report synchronously before serving to prevent Bokeh race condition (#893)
- Coerce sweep bounds/values to declared type (#888)
- Use CDN viewer for rerun and eagerly init recording (#884)

### Performance
- `as_completed()` for parallel result streaming (#891)
- Hoist shared allocations and pre-cache numpy arrays (#886)
- Bypass xarray indexing and cache `get_input_and_results` (#885)
- Batch cache lookups to reduce SQLite round-trips (#883)
- Memoize `to_dataset()` results (#877)
- Speed up RTD docs build (#892)

## [1.78.0] - 2026-04-02

### Added
- `share_axis` parameter on `ResultFloat` for independent y-axis scaling (#881)
- Automatic axiswise scaling when result variables have different units

### Fixed
- pylint E0606: initialize `axiswise_cb` before conditional

## [1.77.0] - 2026-04-02

### Changed
- **Renamed `ResultVar` to `ResultFloat`** with deprecation shim (#880)
- Extract `SCALAR_RESULT_TYPES` constant to DRY up repeated type tuples

### Docs
- Improve `ResultBool` discoverability in docs and docstrings (#879)

## [1.76.0] - 2026-04-01

### Added
- `PaneLayout` option for tab-based multi-dimensional container display (#878)
- Auto-generated examples for container tab layouts
- Bump rerun-sdk and rerun-notebook to 0.31.x (#867)

### Performance
- Eliminate redundant deepcopy in `BenchRunner.run()` (#876)

## [1.75.2] - 2026-03-31

### Fixed
- `.rrd` iframe URLs no longer hardcode `localhost:8051` — CDN viewer uses relative URLs, local/hosted viewer resolves `window.location.origin` at render time via JavaScript, so reports work behind container port mappings and on any Panel server port (#866)
- Panel server uses `port=0` (OS-assigned) when no explicit port is given, preventing `OSError: Address already in use` when other services occupy the default port (#866)
- `_cdn_viewer_versions` cache collision between `_cdn_viewer_url` (filenames) and `_get_cdn_viewer_html` (HTML strings) — split into separate caches (#866)
- Film strip labels now render at constant pixel size regardless of strip dimensions, with horizontal clipping and right-alignment for wide strips (#865)

### Changed
- `show=True` in `BenchRunner.run()` now auto-saves a static HTML report to `reports/` in a background thread (non-blocking), with the path logged for offline viewing. Explicit `save=True` still saves synchronously. (#866)
- **Deprecated `__call__()` in favor of `benchmark()`**: `ParametrizedSweep` subclasses should now override `benchmark()` instead of `__call__()`. The new method removes the need for `self.update_params_from_kwargs(**kwargs)` and `return super().__call__()` boilerplate. The old `__call__()` pattern still works but emits a `DeprecationWarning`. (#864)

### Removed
- `PANEL_PORT` constant from `utils_rrd` — no longer needed since iframe URLs are resolved dynamically (#866)

## [1.74.0] - 2026-03-28

### Added
- **Cartesian Product Animations**: New PIL-based animation system that visualizes how parameter sweep dimensions build upon each other (point → line → grid → stack → film strip) (#feature/manim_summary)
- `BenchCfg.to_cartesian_animation()` method for rendering dimensional progression animations
- Automatic animation embedding in sweep descriptions via `BenchCfg.describe_sweep()`
- `CartesianProductCfg` and `CartesianProductScene` classes for animation configuration and rendering
- `bencher.results.manim_cartesian` module with Shape, StrobeShape, and TimelineShape classes
- **Complete Usage Guide**: New comprehensive `docs/how_to_use_bencher.md` documentation covering sweep types, result types, and best practices
- Tab bar sweep example (`example_tab_bar_sweep.py`) demonstrating UI layout testing with PIL rendering
- Meta example generation system for creating animation galleries
- 10-color pastel palette for dimensional visualization with proper contrast on white backgrounds
- Film strip metaphor for `over_time` dimension with sprocket holes and frame labels
- Strobe/flash animation for `repeat` dimension with tally mark counters

### Changed 
- **Dark Theme Tab Bar**: Report tabs now use dark background with improved contrast and sticky positioning
- Tab bar styling updated with rounded corners, better spacing, and proper hover states
- Meta example generation now includes animation examples in advanced gallery
- Animation rendering uses unique filenames to prevent file path collisions
- Improved tally mark visuals with thicker strikethrough, larger fonts, and centered labels

### Fixed
- Animation filepath collisions resolved with unique filename generation based on animation parameters
- ListProxy pickle serialization issues for multiprocessing compatibility
- Animation size optimization for better performance and smaller file sizes

## [1.73.1] - 2026-03-27

### Fixed
- Generate optimisation reports for all benchmarks, not just the last (#852)
- Include time event in over_time panel labels and default to last (#849)
- Wrap long description strings in generated examples to fit 100-char line limit (#851)
- Override RTD theme CSS to wrap long lines in docs code blocks (#851)

## [1.73.0] - 2026-03-26

### Added
- `bn.sweep()` API with `bounds=(low, high)` support as the unified replacement for `bn.p()` — `bn.p()` still works but emits a `DeprecationWarning` (#838)
- `SweepBase.__call__()` for concise, type-safe sweep configuration: `Cfg.param.theta([0, 0.5, 1.0])` or `Cfg.param.theta(samples=5)` (#838)
- `SweepBase.with_bounds()` for overriding sweep ranges immutably (#838)
- Dict and inline-dict shorthand for `input_vars` in `plot_sweep`: `{"theta": [0, 0.5, 1.0]}`, `{"theta": 5}`, `{"theta": None}` (#842)
- `atexit` handler to stop Panel servers on exit, preventing process hangs after `bn.run(show=True)` (#841)
- Interactive prompt in terminal mode — press Enter to stop servers after viewing results (#841)
- SIGTERM handler chaining — lazily installed only when servers are created, chains to previous handler instead of calling `sys.exit()` (#841)
- `over_time` parameter on `bn.run()` and `BenchRunner.run()` — enables time-series benchmarking without manually creating a `BenchRunCfg` (#848)
- 2-float 2-categorical aggregation example (`agg_list_2_cat`) demonstrating `aggregate=["direction", "scale"]` on a `GradientSurface` class (#845)

### Changed
- `FloatSweep`/`IntSweep` now store user-supplied bounds as param `softbounds` instead of hard bounds, so values outside the defined sweep range are no longer rejected by `update_params_from_kwargs` (#838)
- `BenchRunCfg.with_defaults()` returns a deep copy and merges defaults into caller-provided configs instead of ignoring them (#840)
- `BenchRunCfg.with_defaults()` raises `ValueError` for unknown parameter names to catch typos early (#840)
- Rename `test/test_bn_p.py` to `test/test_sweep_helper.py` to match new `bn.sweep()` API
- Generated over_time examples now pass `over_time=True` via `bn.run()` kwargs instead of setting `run_cfg.over_time` inside the function body (#848)

### Fixed
- `bn.p()` now raises `ValueError` when `max_level` is used with `SweepBase` objects, which require `run_cfg.level` at execution time (#838)
- `bn.sweep()` / `__call__()` reject combining explicit `values` with `bounds`/`samples` to prevent ambiguous configurations (#838)
- Server shutdown is exception-safe — a failing shutdown on one runner no longer prevents cleanup of remaining runners (#841)
- Shutdown errors are logged to stderr instead of silently swallowed (#841)
- Interactive prompt delayed to appear after async server startup logs (#841)
- Optuna plot failures now show diagnostic `Markdown` panels instead of silently swallowing exceptions (#847)
- `to_optuna_plots()` in `bn.run()` shows a diagnostic when `optimize()` returns `None` (#847)
- `logging.warning` when `dropna` removes all rows from optuna trial data (#847)

## [1.72.3] - 2026-03-24

### Fixed
- `aggregate` parameter in `plot_sweep` now produces the correct plot type for remaining dimensions (e.g. heatmap for 2 remaining floats) instead of always forcing a 1D band plot, collapsing all non-x dimensions

## [1.72.2] - 2026-03-23

### Changed
- `git_time_event()` now uses wall-clock time (`datetime.now()`) instead of commit date, producing labels like `"2024-06-15 14:59 abc1234"` so multiple runs on the same commit get distinct over_time labels
- `git_time_event()` uses `git rev-parse --short HEAD` for the canonical abbreviated SHA instead of hardcoded `[:8]` slicing
- `git_time_event()` falls back to `"<timestamp> unknown"` instead of just the timestamp when git is unavailable, keeping the label format consistent
- Removed the second subprocess call (`git log`) from `git_time_event()`, making it lighter for fork-sensitive environments
- Increased `wrap_long_time_labels` wrap width from 20 to 30 characters to accommodate the longer time-event label format
- Docstring documents the recommended import-time caching pattern for fork-safety in threaded environments (ROS 2, DDS, etc.)

### Performance
- Skip redundant dataset copy in `to_dataset()` for REDUCE/MINMAX paths (#826)
- Single-pass reduction avoids `xr.merge()` in `to_dataset()` (#824)
- Replace DataFrame groupby with xarray sel in curve overlay (#822)
- Batch cross-process hash tests into 2 subprocess invocations (#820)
- Add comprehensive `.save()` performance benchmark and report (#825)

## [1.72.1] - 2026-03-22

### Changed
- **Breaking:** `show_aggregated_time_tab` now defaults to `False`. The aggregated "All Time Points" tab doubled `report.save()` embed cost because Panel must pre-compute JSON patches for every slider position in both tabs. Users who need the aggregated view can set `show_aggregated_time_tab=True`. (#818)

### Added
- `report_save_ms` field on `SweepTimings` so downstream users can instrument `report.save()` cost

## [1.71.0] - 2026-03-21

### Added
- Bencher self-introspection: `SweepTimings` instruments `Bench.run_sweep()` to measure phase-level overhead (dataset setup, job submission, execution, cache checks, etc.) (#793)
- `example_self_benchmark` and `example_self_benchmark_over_time` examples for profiling bencher's own overhead (#793)

### Changed
- Rename import alias convention from `import bencher as bch` to `import bencher as bn` across all examples and tests
- Rename `test/test_bch_p.py` to `test/test_bn_p.py`
- Update AST check in `generate_examples.py` to match new `bn` alias

### Fixed
- Fix `ValueError` crash in `to_optuna_plots()` when `over_time=True` — `TimeSnapshot` param conversion only handled `np.datetime64` but pandas returns `pd.Timestamp` (#792)
- Fix `summarise_optuna_study` for single-objective studies — no longer calls `plot_pareto_front` which requires ≥2 objectives (#795)
- Fix `summarise_optuna_study` for multi-objective studies — passes explicit `target` callbacks to `plot_optimization_history` (#795)
- Fix `sweep_var_to_suggest` fall-through for TimeSnapshot/TimeEvent — now explicitly returns `None` instead of raising `ValueError` (#796)
- Auto-compute `total_ms` in `SweepTimings` and add `inspect` fallback (#796)

## [1.70.4] - 2026-03-20

### Fixed
- Fix curve plots using string-typed over_time (TimeEvent) as x-axis instead of the float input variable — explicitly set kdims in `to_curve_ds` to match `to_line_ds` behavior
- Classify TimeEvent as continuous in plot config so it is treated like TimeSnapshot for plotting
- Add TimeEvent support in optuna conversions and trial building

### Removed
- Remove vestigial `iv_time_event` field from BenchCfg (was never populated)

## [1.70.2] - 2026-03-20

### Fixed
- Fix band plots sharing axes across different metrics
- Fix plot server not working with container port forwarding

## [1.70.1] - 2026-03-19

### Fixed
- Fix over_time slider starting at first position instead of last in embedded HTML — Panel's `DiscreteSlider` sets the Bokeh `Slider.title` to `''`, so the JS that matched by `title === "over_time"` never found the slider; now uses Panel State model's widgets map to reliably locate the slider

## [1.66.3] - 2026-03-14

### Fixed
- Force `DiscreteSlider` widget for the `over_time` dimension so string-based `TimeEvent` coordinates get a slider instead of a dropdown

## [1.66.2] - 2026-03-13

### Fixed
- Fix over_time bar chart broken by unconditional image slider routing — numeric `ResultVar` types were incorrectly routed to `_pane_over_time_slider`, causing `FileNotFoundError` and `ValueError`

## [1.66.1] - 2026-03-13

### Fixed
- Fix `DTypePromotionError` crash when `over_time` coordinate type changes between runs (e.g., `time_event=None` → `time_event="v1.0"`)
- Check `over_time` dtype compatibility before concat, discarding incompatible history with a warning instead of crashing
- Include old/new dtypes in the warning message for easier debugging

## [1.66.0] - 2026-03-12

### Added
- Over-time slider support for BarResult: bar charts now show a time slider when `over_time=True` with multiple time points
- Over-time slider support for DistributionResult (BoxWhisker, Violin): distribution plots now show a time slider when `over_time=True` with multiple time points
- New meta-generated examples combining `over_time=True` with `repeats>1` for 0-1 float input configurations
- Tests for over_time + repeats across bar, distribution, and curve plot types

## [1.65.0] - 2026-03-11

### Fixed
- Fix non-deterministic `hash_persistent()` in 9 result variable classes that broke `over_time` history cache lookups across process invocations
- Fix `ResultVec.hash_persistent()` not including `size` in hash, causing cache key collisions for vectors of different sizes
- Add `_hash_slots()` helper that hashes all `__slots__` by default, with explicit `_hash_exclude` for non-deterministic runtime attributes (`obj`, `container`)
- Add comprehensive auto-discovery tests that will catch any future Result class missing deterministic hashing

## [1.64.0] - 2026-03-11

### Added
- `init_singleton()` now returns a context manager that auto-resets singleton state when first-time init raises, eliminating manual `_seen`/`_instances` cleanup boilerplate
- `reset_singleton()` public classmethod for explicitly clearing singleton state
- Thread-safe singleton operations via internal `threading.Lock`
- Full backward compatibility preserved — `if self.init_singleton():` works identically

## [1.63.0] - 2026-03-09

### Fixed
- Over-time slider now correctly defaults to the most recent time point instead of the first (#756)
- Fixed `DiscreteSlider` dict options handling — `list(w.options)` returned string keys instead of actual values, causing the slider to silently fall back to the first time point
- Added guard against empty widget options to prevent `IndexError`
- Narrowed slider default logic to only target the `over_time` widget, avoiding unintended side effects on other widgets

## [1.62.0] - 2026-03-06

### Added
- Over-time slider for visualizing benchmark results across time steps (#729, #730)
- Single-page scrollable gallery overview with CSS grid cards (#731)
- Feature-specific meta generators for result types, plot types, optimization, sampling, const vars, and statistics (#732)
- `bch.run()` API for simplified benchmark execution (#732)
- Inline rerun viewer support with `rerun_to_pane()` (#717)
- Prebuilt devcontainer image support via GHCR (#136)
- 3D visualization example
- Image, video, and volume plot type examples (#747)
- Full `ComposeType` support across all composable container backends (#746)
- Composable container gallery examples (#746)

### Changed
- Replaced notebook pipeline with Python examples + HTML reports (#734)
- Consolidated generated examples from `meta/generated/` to `example/generated/` and tracked in Git (#735)
- Updated rerun-sdk from 0.29.x to 0.30.1 (#725)
- Replaced `rerun.legacy_notebook` with `rerun_notebook.Viewer`
- Gallery now uses real iframe thumbnails with auto-crop via ResizeObserver
- Skip Tabs sidebar for single-tab reports
- Notebook generation is now fully deterministic across runs
- Updated meta generator `__main__` blocks to use `bch.run()`
- Switched gallery thumbnails from selenium+Firefox to playwright+Chromium (#741)
- Consolidated result types into a single gallery section with sub-headings (#748)
- Improved const vars documentation examples (#749)
- Improved statistics examples to showcase distinct bencher features (#751)

### Fixed
- Panel server dying on `bch.run(show=True)` (#732)
- Widget location fixed by wrapping HoloMaps in `pn.pane.HoloViews` (#730)
- Parameterized sweep benchmark naming when param counter exceeds 5 digits
- Over-time rendering for heatmap/line plots
- `const_vars` hash not chaining accumulated `hash_val` (#723)
- RTD build configuration for Playwright dependencies
- Over-time scrubber not appearing in static HTML
- Surface plot 3D rendering using xarray DataArray directly instead of pivot_table (#747)
- Gallery thumbnails broken on ReadTheDocs (#741)
- Overlay duration bug in composable containers (#746)
- apt package name `libasound2` → `libasound2t64` for Ubuntu 24.04

### Dependencies
- Bumped `rerun-sdk` and `rerun-notebook` to >= 0.30.1
- Updated `actions/checkout` from 4 to 6
- Updated `prefix-dev/setup-pixi` from 0.9.3 to 0.9.4
- Various dependency updates via Dependabot

## [1.60.0] - 2026-01-24

### Changed
- Updated numpy version constraint from `<=2.2.6` to `<=2.4.1` to support latest numpy releases
- Updated all dependencies to latest compatible versions through pixi update

### Fixed
- Resolved historical hvplot compatibility issues with numpy 2.x that were preventing updates

### Technical Details
- The numpy version limitation was due to binary compatibility issues between numpy 2.0 and hvplot that occurred when numpy 2.0 was released in June 2024
- These issues have been fully resolved in the ecosystem, with hvplot 0.12.2 now fully compatible with numpy 2.4.x
- All tests pass successfully with the updated dependencies

## [0.3.10]

Before changelogs
