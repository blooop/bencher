# 02 - Directory Structure

## Full Annotated Tree

### Core Package (`bencher/`)

```
bencher/
├── __init__.py                          # Public API exports (all major classes, sweep types, result types)
├── bencher.py                           # Main Bench class - orchestrates parameter sweeps and result collection
├── bench_cfg.py                         # Configuration classes: BenchPlotSrvCfg, BenchRunCfg, BenchCfg, DimsCfg
├── bench_runner.py                      # BenchRunner - higher-level interface for multiple benchmark runs
├── bench_plot_server.py                 # BenchPlotServer - serves cached results via Panel web server
├── bench_report.py                      # BenchReport - generates and publishes HTML reports
├── caching.py                           # CachedParams - legacy caching wrapper using diskcache
├── class_enum.py                        # ClassEnum/ExampleEnum - factory pattern for enum-to-class mapping
├── factories.py                         # Factory functions (create_bench, create_bench_runner) to break circular deps
├── flask_server.py                      # Flask server for local file serving (used by Rerun integration)
├── job.py                               # Job, JobFuture, FutureCache, Executors, JobFunctionCache - execution primitives
├── optuna_conversions.py                # Optuna integration - type conversions, grid search, parameter importance
├── result_collector.py                  # ResultCollector - manages xarray dataset creation and result storage
├── sample_order.py                      # SampleOrder enum (INORDER, REVERSED) for sweep traversal order
├── sweep_executor.py                    # SweepExecutor - variable conversion and cache initialization
├── utils.py                             # General utilities: hashing, path generation, color math, string formatting
├── utils_rerun.py                       # Rerun 3D visualization integration utilities
├── video_writer.py                      # VideoWriter - image sequence to video conversion using moviepy
├── worker_job.py                        # WorkerJob dataclass - encapsulates single benchmark invocation
├── worker_manager.py                    # WorkerManager - worker function configuration and validation
│
├── variables/                           # Parameter sweep and result variable definitions
│   ├── __init__.py                      # Package marker
│   ├── sweep_base.py                    # SweepBase abstract base class for all sweep types
│   ├── inputs.py                        # Concrete sweep types: IntSweep, FloatSweep, BoolSweep, StringSweep, EnumSweep, YamlSweep
│   ├── results.py                       # Result variable types: ResultVar, ResultBool, ResultVec, ResultHmap, etc.
│   ├── parametrised_sweep.py            # ParametrizedSweep - base class for user-defined sweep configurations
│   ├── singleton_parametrized_sweep.py   # ParametrizedSweepSingleton - singleton variant
│   └── time.py                          # TimeSnapshot, TimeEvent - temporal benchmark variables
│
├── results/                             # Result containers and visualization classes
│   ├── __init__.py                      # Package marker
│   ├── bench_result_base.py             # BenchResultBase - core result handling, reduction, optimization
│   ├── bench_result.py                  # BenchResult - composite class inheriting all visualization types
│   ├── float_formatter.py               # Float formatting utilities for display
│   ├── laxtex_result.py                 # LaTeX result generation
│   ├── video_result.py                  # VideoResult - video-based benchmark results
│   ├── video_summary.py                 # VideoSummaryResult - summarized video outputs with labels
│   ├── video_controls.py                # VideoControls - interactive video playback widgets
│   ├── volume_result.py                 # VolumeResult - 3D volume plots using Plotly
│   ├── histogram_result.py              # HistogramResult - histogram distribution visualization
│   ├── optuna_result.py                 # OptunaResult - Optuna optimization result display
│   ├── dataset_result.py                # DataSetResult - raw xarray dataset exploration
│   ├── explorer_result.py               # ExplorerResult - interactive data explorer interface
│   │
│   ├── holoview_results/                # HoloViews-based interactive plot results
│   │   ├── __init__.py                  # Package marker
│   │   ├── holoview_result.py           # HoloviewResult base class for all interactive 2D/3D plots
│   │   ├── scatter_result.py            # ScatterResult - 2D scatter plots
│   │   ├── line_result.py               # LineResult - line/curve plots with tap interaction
│   │   ├── curve_result.py              # CurveResult - smooth curve interpolations
│   │   ├── bar_result.py                # BarResult - bar/column charts
│   │   ├── heatmap_result.py            # HeatmapResult - 2D heatmaps with tap interaction
│   │   ├── surface_result.py            # SurfaceResult - 3D surface plots
│   │   ├── table_result.py              # TableResult - tabular data display
│   │   ├── tabulator_result.py          # TabulatorResult - interactive Tabulator.js tables
│   │   │
│   │   └── distribution_result/         # Statistical distribution visualizations
│   │       ├── __init__.py              # Package marker
│   │       ├── distribution_result.py   # DistributionResult base class
│   │       ├── box_whisker_result.py    # BoxWhiskerResult - box-and-whisker plots
│   │       ├── violin_result.py         # ViolinResult - violin plots
│   │       └── scatter_jitter_result.py # ScatterJitterResult - jittered scatter distributions
│   │
│   └── composable_container/            # Multi-result composition framework
│       ├── __init__.py                  # Package marker
│       ├── composable_container_base.py # ComposableContainerBase, ComposeType enum
│       ├── composable_container_dataframe.py  # ComposableContainerDataframe
│       ├── composable_container_panel.py      # ComposableContainerPanel - Panel-based layouts
│       └── composable_container_video.py      # ComposableContainerVideo, RenderCfg
│
├── plotting/                            # Plot configuration and filtering
│   ├── __init__.py                      # Package marker
│   ├── plot_filter.py                   # PlotFilter, VarRange, PlotMatchesResult - plot type matching
│   └── plt_cnt_cfg.py                   # PltCntCfg - plot count configuration from benchmark dimensions
│
└── example/                             # Comprehensive examples (see Section: Example Organization)
    ├── __init__.py                      # Package marker
    ├── benchmark_data.py                # ExampleBenchCfg base class for examples
    ├── example_utils.py                 # Shared example utilities
    ├── example_simple.py                # Basic simple example
    ├── example_simple_float.py          # Simple float parameter example (recommended starting point)
    ├── ... (50+ example files)          # Various examples organized by feature
    │
    ├── inputs_0D/                       # 0-dimensional examples (no inputs)
    ├── inputs_0_float/                  # Categorical-only examples
    ├── inputs_1D/                       # 1D parameter sweep examples
    ├── inputs_2D/                       # 2D parameter sweep examples
    ├── inputs_1_float/                  # 1 float + varying categorical examples
    ├── inputs_2_float/                  # 2 float + varying categorical examples
    ├── inputs_3_float/                  # 3 float + varying categorical examples
    ├── meta/                            # Meta examples and doc generation
    │   ├── generate_examples.py         # Documentation notebook generator
    │   ├── generate_meta.py             # Meta-example generator
    │   ├── example_meta.py              # Base meta-example
    │   ├── example_meta_cat.py          # Categorical meta-example
    │   ├── example_meta_float.py        # Float meta-example
    │   └── example_meta_levels.py       # Level-based meta-example
    ├── optuna/                          # Optuna optimization examples
    ├── experimental/                    # Experimental/WIP examples
    └── shelved/                         # Archived/deprecated examples
```

## Organization Principles

### 1. Component Type (Root Level)
The core package files at `bencher/` root are organized by **architectural component**: orchestration (`bencher.py`), configuration (`bench_cfg.py`), execution (`job.py`, `sweep_executor.py`, `worker_*.py`), reporting (`bench_report.py`), and integration (`optuna_conversions.py`, `utils_rerun.py`).

### 2. Parameter/Result Type (Variables)
The `bencher/variables/` package separates concerns into **inputs** (sweep parameter types), **results** (output variable types), **time** (temporal variables), and the **base framework** (`parametrised_sweep.py`, `sweep_base.py`).

### 3. Visualization Type (Results)
The `bencher/results/` package is organized by **visualization backend and chart type**: HoloViews-based plots, video results, composable containers, and statistical distributions.

### 4. Input Dimensionality (Examples)
The `bencher/example/` directory is organized by **number and type of input parameters**: `inputs_0D` through `inputs_3_float`, plus categories for specific features (meta, optuna, experimental). This makes it easy to find examples matching a user's parameter configuration.

### 5. Plot Dimensionality (Distribution Results)
The `distribution_result/` subdirectory groups visualizations that specifically handle **repeated measurements** (distributions): box-whisker, violin, and scatter-jitter plots.

## File Statistics

| Directory | Python Files | Purpose |
|-----------|-------------|---------|
| `bencher/` (root) | 19 | Core framework |
| `bencher/variables/` | 7 | Parameter definitions |
| `bencher/results/` | 29 | Visualization classes |
| `bencher/plotting/` | 3 | Plot configuration |
| `bencher/example/` | ~120 | Examples and docs |
| **Total** | **~178** | |
