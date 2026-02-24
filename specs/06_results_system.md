# 06 - Results & Visualization System

## BenchResultBase (`results/bench_result_base.py:82`)

Core base class for all benchmark results. Key state:
- `bench_cfg: BenchCfg` — benchmark configuration
- `ds: xr.Dataset` — N-dimensional result dataset
- `plt_cnt_cfg: PltCntCfg` — plot count configuration

Key methods: `to_xarray()`, `to_pandas()`, `to_hv_dataset()`, `filter()` (evaluates PlotFilter), `map_plots()`, `get_optimal_value_indices()`, `get_optimal_inputs()`.

## Visualization Types

> See [04_class_hierarchy.md](04_class_hierarchy.md) for the full BenchResult MI pattern.

| Type | Data Shape | Output |
|------|-----------|--------|
| **ScatterResult** | 0 float, 0+ cat, 1 repeat | HoloViews Points/Scatter |
| **LineResult** | 1 float, 0+ cat, 1 repeat | HoloViews Curve with optional tap interaction |
| **HeatmapResult** | 0+ float, 0+ cat, 2+ total inputs | HoloViews HeatMap with optional tap containers |
| **SurfaceResult** | 2+ float, 0+ cat | 3D Plotly surface plot |
| **VolumeResult** | 3 float, 0 cat | 3D Plotly volume visualization |
| **BarResult** | Categorical + numeric | HoloViews Bars |
| **CurveResult** | Similar to Line | Smooth interpolated curves with std dev |
| **BoxWhiskerResult** | Any, repeats > 1 | Box-and-whisker (median, quartiles, outliers) |
| **ViolinResult** | Any, repeats > 1 | Violin plots (full distribution shape) |
| **ScatterJitterResult** | Any, repeats > 1 | Jittered scatter (individual measurements) |
| **HistogramResult** | Numeric results | Histogram frequency distribution |
| **VideoResult** | ResultVideo/ResultImage | Video playback with controls |
| **VideoSummaryResult** | Media results | Labeled video/image grid |
| **DataSetResult** | Any (always available) | Raw xarray dataset view |
| **OptunaResult** | Any (with Optuna) | Optimization history, importance, Pareto front |
| **TableResult / TabulatorResult** | Any | Static or interactive table display |

## ReduceType Enum (`bench_result_base.py:41`)

Controls how repeated measurements are aggregated:

| Value | Effect |
|-------|--------|
| `AUTO` | Automatic selection based on repeat count |
| `SQUEEZE` | Remove dimensions of length 1 |
| `REDUCE` | Mean + standard deviation over repeat dimension |
| `MINMAX` | Min/max range over repeat dimension |
| `NONE` | No reduction |

## PlotFilter System (`plotting/plot_filter.py`)

**VarRange** (`plot_filter.py:9`): Bounded integer range for matching dimensionality. `lower_bound`/`upper_bound` (None = unbounded).

**PlotFilter** (`plot_filter.py:68`): Dataclass specifying requirements for a plot type via VarRange fields: `float_range`, `cat_range`, `vector_len`, `result_vars`, `panel_range`, `repeats_range`, `input_range`.

**PlotMatchesResult** (`plot_filter.py:95`): Stores filter evaluation result with `overall: bool` and debug info.

## Plot Deduction Algorithm

In `BenchResult.to_auto()` (`bench_result.py:146-190`):

1. **Classify inputs**: `PltCntCfg.generate_plt_cnt_cfg()` (`plt_cnt_cfg.py:36-80`) counts float inputs (`IntSweep`, `FloatSweep`, `TimeSnapshot`), categorical inputs (`EnumSweep`, `BoolSweep`, `StringSweep`, `YamlSweep`), panel-type results, and repeats.

2. **Get callbacks** from `default_plot_callbacks()` (`bench_result.py:99-122`): scatter, line, heatmap, volume, box_whisker, violin, scatter_jitter, surface, video_summary, dataset, optuna.

3. **Filter**: For each callback, evaluate its `PlotFilter` against `PltCntCfg`. All matching plots are included (additive, not exclusive).

4. **Render**: Each matching callback's `to_plot()` method produces a Panel pane, assembled into a Column layout.

## ComposableContainer System (`results/composable_container/`)

Framework for combining multiple result types into composite layouts.

- **ComposeType** enum: `right`, `down`, `sequence`, `overlay` (with `flip()` method)
- **ComposableContainerPanel** — Panel Row/Column layouts with CSS styling
- **ComposableContainerVideo** — Video composition via moviepy with `RenderCfg`
- **ComposableContainerDataset** — DataFrame-based composition
