# Results Visualization Architecture Diagrams

## Current Architecture (Tightly Coupled)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         bencher Package                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐         ┌─────────────────────────────────────┐  │
│  │    Bench     │────────>│       BenchResult                   │  │
│  │  (executor)  │ creates │  (multiple inheritance hell)        │  │
│  └──────────────┘         │                                     │  │
│                            │  inherits from:                     │  │
│  ┌──────────────┐         │  - VolumeResult                     │  │
│  │  BenchCfg    │────────>│  - BoxWhiskerResult                 │  │
│  │ (config)     │ passed  │  - ViolinResult                     │  │
│  └──────────────┘   to    │  - ScatterJitterResult              │  │
│                            │  - ScatterResult                    │  │
│                            │  - LineResult                       │  │
│                            │  - BarResult                        │  │
│                            │  - HeatmapResult                    │  │
│                            │  - CurveResult                      │  │
│                            │  - SurfaceResult                    │  │
│                            │  - HoloviewResult                   │  │
│                            │  - HistogramResult                  │  │
│                            │  - VideoSummaryResult               │  │
│                            │  - DataSetResult                    │  │
│                            │  - OptunaResult                     │  │
│                            └─────────────────────────────────────┘  │
│                                          ↓                           │
│                            ┌─────────────────────────────────────┐  │
│                            │    BenchResultBase                  │  │
│                            │    (753 lines - data + viz mixed)   │  │
│                            │                                     │  │
│                            │  Contains:                          │  │
│                            │  - xr.Dataset (data storage)        │  │
│                            │  - to_pandas() (data)               │  │
│                            │  - to_hv_dataset() (viz!)           │  │
│                            │  - map_plot_panes() (viz!)          │  │
│                            │  - _to_panes_da() (viz!)            │  │
│                            │  - Returns pn.Column (viz!)         │  │
│                            └─────────────────────────────────────┘  │
│                                          ↓                           │
│                            ┌─────────────────────────────────────┐  │
│                            │   External Dependencies             │  │
│                            │   (all required)                    │  │
│                            │                                     │  │
│                            │   - xarray         (data)           │  │
│                            │   - pandas         (data)           │  │
│                            │   - holoviews      (viz)            │  │
│                            │   - hvplot         (viz)            │  │
│                            │   - panel          (viz/UI)         │  │
│                            │   - plotly         (viz/3D)         │  │
│                            │   - bokeh          (viz backend)    │  │
│                            └─────────────────────────────────────┘  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘

Problems:
❌ Cannot remove holoviews without breaking everything
❌ Cannot add matplotlib backend without modifying core
❌ BenchResult has 14+ parent classes (maintenance nightmare)
❌ Data and visualization logic mixed in BenchResultBase
❌ Heavy dependencies even if you only want data export
```

---

## Proposed Architecture (Decoupled with Adapters)

```
┌────────────────────────────────────────────────────────────────────────┐
│                      bencher-core (lightweight)                         │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐         ┌────────────────────────────────────────┐  │
│  │    Bench     │────────>│      BenchResult (facade)              │  │
│  │  (executor)  │ creates │                                        │  │
│  └──────────────┘         │  Responsibilities:                     │  │
│                            │  - Delegate data ops to ResultData     │  │
│  ┌──────────────┐         │  - Delegate viz to VisualizationAdapter│  │
│  │ResultMetadata│────────>│  - Provide unified API                 │  │
│  │  (config)    │ creates │                                        │  │
│  └──────────────┘         │  Methods:                              │  │
│                            │  - to_pandas() → ResultData            │  │
│                            │  - plot(type) → Adapter                │  │
│                            │  - use_backend() → Switch adapter      │  │
│                            └────────────────────────────────────────┘  │
│                                     ↓           ↓                       │
│                        ┌────────────┘           └────────────────┐     │
│                        ↓                                         ↓     │
│  ┌────────────────────────────────────────┐  ┌─────────────────────┐  │
│  │      BenchResultData                   │  │ VisualizationRegistry│ │
│  │      (pure data, no viz)               │  │   (plugin system)   │  │
│  │                                        │  │                     │  │
│  │  Contains:                             │  │ Registered backends:│  │
│  │  - xr.Dataset storage                  │  │ - "holoviews"       │  │
│  │  - object_references (non-array data)  │  │ - "plotly"          │  │
│  │  - datasets (ResultDataSet)            │  │ - "matplotlib"      │  │
│  │                                        │  │ - "custom"          │  │
│  │  Methods (data only):                  │  │                     │  │
│  │  - to_xarray() → xr.Dataset            │  │ Methods:            │  │
│  │  - to_pandas() → pd.DataFrame          │  │ - register(adapter) │  │
│  │  - to_dict() → dict                    │  │ - get_adapter(name) │  │
│  │  - reduce(type) → xr.Dataset           │  │ - set_default(name) │  │
│  │  - aggregate(dims) → xr.Dataset        │  │                     │  │
│  │  - filter_dims(**filters) → filtered   │  │                     │  │
│  └────────────────────────────────────────┘  └─────────────────────┘  │
│                      ↓                                  ↑               │
│        ┌────────────────────────────┐                  │               │
│        │  Core Dependencies         │                  │               │
│        │  (minimal, required)       │                  │               │
│        │                            │                  │               │
│        │  - xarray     (data)       │                  │               │
│        │  - pandas     (data)       │                  │               │
│        │  - numpy      (data)       │                  │               │
│        │  - param      (config)     │                  │               │
│        │  NO VIZ LIBRARIES!         │                  │               │
│        └────────────────────────────┘                  │               │
│                                                         │               │
└─────────────────────────────────────────────────────────┼───────────────┘
                                                          │
                                                          │ Plugin Interface
                     ┌────────────────────────────────────┼───────────────┐
                     │ VisualizationAdapter (Protocol)    │               │
                     ├────────────────────────────────────┴───────────────┤
                     │                                                    │
                     │  Required Methods:                                 │
                     │  - name() → str                                    │
                     │  - supported_plot_types() → List[str]              │
                     │  - render(data, type, **kw) → plot                 │
                     │  - auto_plot(data, **kw) → composed_plots          │
                     │  - compose_layout(plots, type) → layout            │
                     │                                                    │
                     └────────────────────────────────────┬───────────────┘
                                                          │
          ┌──────────────────┬────────────────┬──────────┴──────────┬────────────────┐
          ↓                  ↓                ↓                     ↓                ↓
┌──────────────────┐ ┌──────────────┐ ┌───────────────────┐ ┌─────────────┐ ┌────────────┐
│bencher-viz-      │ │bencher-viz-  │ │bencher-viz-       │ │bencher-viz- │ │bencher-viz-│
│holoviews         │ │plotly        │ │matplotlib         │ │altair       │ │custom      │
│(separate repo)   │ │(separate)    │ │(separate)         │ │(separate)   │ │(community!)│
├──────────────────┤ ├──────────────┤ ├───────────────────┤ ├─────────────┤ ├────────────┤
│HoloviewsAdapter  │ │PlotlyAdapter │ │MatplotlibAdapter  │ │AltairAdapter│ │CustomAdapter│
│                  │ │              │ │                   │ │             │ │            │
│Implements:       │ │Implements:   │ │Implements:        │ │Implements:  │ │Implements: │
│- scatter         │ │- scatter     │ │- scatter          │ │- scatter    │ │- custom1   │
│- line            │ │- line        │ │- line             │ │- line       │ │- custom2   │
│- bar             │ │- bar         │ │- bar              │ │- bar        │ │            │
│- heatmap         │ │- surface (3D)│ │- publication figs │ │- interactive│ │            │
│- surface         │ │- volume (3D) │ │- static exports   │ │- web-based  │ │            │
│- distribution    │ │- 3D plots    │ │- PDF/SVG output   │ │             │ │            │
│- video           │ │              │ │                   │ │             │ │            │
│- table           │ │              │ │                   │ │             │ │            │
│                  │ │              │ │                   │ │             │ │            │
│Dependencies:     │ │Dependencies: │ │Dependencies:      │ │Dependencies:│ │Dependencies│
│- bencher-core    │ │- bencher-core│ │- bencher-core     │ │- bencher-   │ │- bencher-  │
│- holoviews       │ │- plotly      │ │- matplotlib       │ │  core       │ │  core      │
│- hvplot          │ │              │ │- seaborn (opt)    │ │- altair     │ │- ???       │
│- panel           │ │              │ │                   │ │             │ │            │
│- bokeh           │ │              │ │                   │ │             │ │            │
└──────────────────┘ └──────────────┘ └───────────────────┘ └─────────────┘ └────────────┘

Benefits:
✅ Visualization plugins in separate repositories
✅ Core has minimal dependencies (xarray, pandas)
✅ Easy to add new backends (matplotlib, plotly, altair, etc.)
✅ Users choose which viz backends to install
✅ Community can create custom adapters
✅ Backward compatible via facade pattern
```

---

## Data Flow: Before vs. After

### BEFORE (Current)

```
User Code
   ↓
bench.run_sweep()
   ↓
Bench creates BenchResult
   ↓
BenchResult.__init__() calls 14+ parent __init__()
   │
   ├─> VolumeResult.__init__()
   ├─> BoxWhiskerResult.__init__()
   ├─> ScatterResult.__init__()
   ├─> LineResult.__init__()
   ├─> ... (10 more)
   └─> BenchResultBase.__init__()
           │
           └─> Initializes xr.Dataset
               Initializes Panel containers
               Initializes HoloViews state

result.to_scatter()  ← Calls method from ScatterResult class
   ↓
ScatterResult.to_scatter()
   ↓
self.to_hv_dataset()  ← From BenchResultBase
   ↓
hv.Dataset(self.ds)
   ↓
hvplot.scatter()
   ↓
Returns pn.panel with embedded HoloViews plot

❌ Visualization tightly coupled at every step
```

### AFTER (Proposed)

```
User Code
   ↓
bench.run_sweep()
   ↓
Bench creates BenchResult (facade)
   │
   ├─> Creates BenchResultData (data only)
   │      └─> Initializes xr.Dataset
   │          NO visualization dependencies
   │
   └─> Stores reference to VisualizationRegistry

result.plot("scatter")  ← Facade method
   ↓
BenchResult.plot()
   ↓
registry.get_adapter(self._backend)
   ↓
HoloviewsAdapter.render(self.data, "scatter")
   │
   ├─> Converts BenchResultData → hv.Dataset
   ├─> Creates scatter plot
   └─> Returns plot in adapter's format

OR switch backend:

result.use_backend("plotly").plot("scatter")
   ↓
PlotlyAdapter.render(self.data, "scatter")
   │
   ├─> Converts BenchResultData → plotly data format
   ├─> Creates scatter plot
   └─> Returns plotly figure

✅ Visualization decoupled via adapter pattern
✅ Easy to switch backends
✅ Core code knows nothing about viz libraries
```

---

## Plugin Registration Flow

```
1. User installs viz plugin:
   $ pip install bencher-viz-holoviews

2. User imports bencher:
   from bencher import Bench

3. User imports viz plugin (auto-registers):
   import bencher_viz_holoviews

   bencher_viz_holoviews/__init__.py:
       from .adapter import HoloviewsAdapter
       from bencher.visualization import VisualizationRegistry
       VisualizationRegistry.register(HoloviewsAdapter)
       # First registered becomes default

4. Now adapter is available:
   result.plot("scatter")  ← Uses holoviews by default

5. Install another backend:
   $ pip install bencher-viz-plotly

   import bencher_viz_plotly  ← Auto-registers

6. Explicitly choose backend:
   result.use_backend("plotly").plot("scatter")

7. Or set new default:
   VisualizationRegistry.set_default("plotly")
   result.plot("scatter")  ← Now uses plotly
```

---

## Directory Structure Comparison

### BEFORE

```
bencher/
├── pyproject.toml           (requires: xarray, pandas, holoviews, hvplot, panel, plotly)
├── bencher/
│   ├── __init__.py
│   ├── bencher.py           (Bench class)
│   ├── bench_cfg.py
│   ├── bench_runner.py
│   ├── results/
│   │   ├── bench_result_base.py        ← 753 lines (data + viz mixed)
│   │   ├── bench_result.py             ← Multiple inheritance from 14+ classes
│   │   ├── video_result.py
│   │   ├── volume_result.py
│   │   ├── histogram_result.py
│   │   ├── holoview_results/
│   │   │   ├── holoview_result.py      ← 346 lines (HoloViews base)
│   │   │   ├── scatter_result.py
│   │   │   ├── line_result.py
│   │   │   ├── bar_result.py
│   │   │   ├── curve_result.py
│   │   │   ├── heatmap_result.py
│   │   │   ├── surface_result.py
│   │   │   ├── table_result.py
│   │   │   └── distribution_result/
│   │   │       ├── box_whisker_result.py
│   │   │       ├── violin_result.py
│   │   │       └── scatter_jitter_result.py
│   │   └── composable_container/
│   │       ├── composable_container_base.py
│   │       ├── composable_container_panel.py
│   │       └── ...
│   └── plotting/
│       └── plot_filter.py
└── ...

❌ Everything in one repo
❌ Cannot separate viz from core
```

### AFTER

```
bencher-core/                           (separate repo)
├── pyproject.toml                      (requires: xarray, pandas ONLY)
├── bencher/
│   ├── __init__.py
│   ├── bencher.py                      (Bench class)
│   ├── bench_cfg.py
│   ├── bench_runner.py
│   ├── results/
│   │   ├── bench_result_data.py        ← NEW (data only, ~200 lines)
│   │   ├── result_metadata.py          ← NEW (dataclass)
│   │   └── bench_result.py             ← REFACTORED (facade, ~150 lines)
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── registry.py                 ← NEW (plugin system)
│   │   └── adapter.py                  ← NEW (protocol definition)
│   └── ...

bencher-viz-holoviews/                  (separate repo!)
├── pyproject.toml                      (requires: bencher-core, holoviews, hvplot, panel)
├── bencher_viz_holoviews/
│   ├── __init__.py                     (auto-register adapter)
│   ├── adapter.py                      (HoloviewsAdapter)
│   ├── renderer.py                     (core rendering)
│   ├── plot_filter.py                  (moved from core)
│   ├── layout.py                       (ComposableLayout)
│   ├── plots/
│   │   ├── __init__.py
│   │   ├── scatter.py
│   │   ├── line.py
│   │   ├── bar.py
│   │   ├── curve.py
│   │   ├── heatmap.py
│   │   ├── surface.py
│   │   ├── table.py
│   │   ├── video.py
│   │   └── distribution/
│   │       ├── box_whisker.py
│   │       ├── violin.py
│   │       └── scatter_jitter.py
│   └── utils.py
└── tests/

bencher-viz-plotly/                     (separate repo, future)
├── pyproject.toml                      (requires: bencher-core, plotly)
├── bencher_viz_plotly/
│   ├── __init__.py
│   ├── adapter.py
│   └── plots/
│       ├── scatter.py
│       ├── surface.py
│       └── volume.py

✅ Separate repositories
✅ Independent versioning
✅ Optional viz dependencies
✅ Community can contribute new backends
```

---

## Backward Compatibility Strategy

```python
# OLD API (still works)
result.to_scatter()
result.to_line()
result.to_auto_plots()

# Implemented as:
class BenchResult:
    def to_scatter(self, **kwargs):
        """Legacy method - delegates to adapter"""
        import warnings
        warnings.warn(
            "to_scatter() is deprecated, use plot('scatter') instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.plot("scatter", **kwargs)

    def to_line(self, **kwargs):
        """Legacy method - delegates to adapter"""
        import warnings
        warnings.warn(
            "to_line() is deprecated, use plot('line') instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.plot("line", **kwargs)

    def to_auto_plots(self, **kwargs):
        """Legacy method - delegates to adapter"""
        import warnings
        warnings.warn(
            "to_auto_plots() is deprecated, use auto_plot() instead",
            DeprecationWarning,
            stacklevel=2
        )
        return self.auto_plot(**kwargs)

# NEW API (recommended)
result.plot("scatter")
result.plot("line")
result.auto_plot()
result.use_backend("plotly").plot("scatter")
```

---

## Summary: Key Architectural Changes

| Aspect | Before | After |
|--------|--------|-------|
| **Data Storage** | BenchResultBase (753 lines, data+viz) | BenchResultData (~200 lines, data only) |
| **Visualization** | 14+ classes with multiple inheritance | Plugin adapters (separate repos) |
| **Core Dependencies** | xarray, pandas, holoviews, hvplot, panel, plotly | xarray, pandas (minimal!) |
| **Extensibility** | Fork repo, modify core | Create plugin package |
| **Backend Switching** | Impossible (hardcoded) | Easy (registry.set_default) |
| **Testing** | Data + viz tested together | Data and viz tested independently |
| **Maintenance** | Single monolithic repo | Core + plugins (independent versioning) |
| **Installation** | All deps required | Choose viz plugins (bencher[viz-holoviews]) |

---

**Conclusion:** The adapter pattern with plugin registry provides a clean separation between data management and visualization, enabling the visualization code to live in separate repositories while maintaining backward compatibility and flexibility for future backends.
