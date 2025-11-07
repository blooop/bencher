# Results Visualization Cleanup Proposal

**Date:** 2025-11-07
**Goal:** Decouple visualization code from core benchmarking to enable separate repository maintenance

## Executive Summary

The current bencher results system tightly couples data management with visualization rendering. This proposal outlines a strategy to separate visualization concerns into a plugin-based architecture, allowing visualization code to live in a separate repository while maintaining backward compatibility.

**Key Challenges:**
- BenchResultBase mixes data storage (xarray) with UI rendering (Panel, HoloViews)
- Multiple inheritance pattern in BenchResult creates tight coupling
- Visualization libraries (holoviews, hvplot, panel, plotly) embedded throughout
- BenchCfg required in all result constructors

**Proposed Solution:**
Introduce a **Visualization Adapter Pattern** with plugin-based rendering backends, separating data representation from presentation.

---

## 1. Current Architecture Analysis

### 1.1 Component Structure

```
Core Components (bencher-core):
├── Bench/BenchRunner          → Execute benchmarks
├── BenchCfg/BenchRunCfg        → Configuration
├── ParametrizedSweep           → Parameter definitions
└── Result Variables            → Result type definitions

Results + Visualization (bencher-results):
├── BenchResultBase             → Data + Visualization foundation (753 lines)
│   ├── xr.Dataset storage
│   ├── Panel layout methods
│   └── Recursive rendering logic
├── BenchResult                 → Aggregator using multiple inheritance (14+ classes)
├── HoloviewResult              → Interactive plotting base (346 lines)
│   ├── ScatterResult, LineResult, BarResult, etc. (8+ plot types)
│   └── DistributionResult family (3+ plot types)
├── VolumeResult                → Plotly 3D visualizations
├── VideoResult/VideoSummary    → Media-based results
└── ComposableContainer         → Layout composition system
```

### 1.2 Dependency Graph

```
Bench → BenchResult → BenchResultBase
                    ↓
        [Multiple Inheritance from 14+ classes]
                    ↓
        ┌───────────┴───────────┐
        ↓                       ↓
    HoloviewResult        VolumeResult
        ↓                       ↓
    holoviews               plotly
    hvplot
    panel
        ↓                       ↓
    xarray ←──────────────────┘
```

**Critical Dependencies:**
- `xarray` → Core data structure (cannot remove without major refactor)
- `panel` → UI layouts and containers
- `holoviews` → Interactive chart creation
- `hvplot` → xarray/pandas plotting convenience layer
- `plotly` → 3D surface/volume plots

### 1.3 High Coupling Points

| Component | Coupling Type | Impact | Severity |
|-----------|---------------|--------|----------|
| **BenchResultBase.ds** | xarray.Dataset | Data structure embedded | CRITICAL |
| **BenchResultBase methods** | Return pn.Column/pn.Row | Panel UI in data layer | HIGH |
| **BenchResult inheritance** | 14+ base classes | Monolithic aggregator | HIGH |
| **HoloviewResult.to_hv_dataset()** | hv.Dataset conversion | Tight HoloViews coupling | HIGH |
| **Recursive layout (_to_panes_da)** | ComposableContainerPanel creation | Hardcoded layout strategy | MEDIUM |
| **PlotFilter integration** | Validation in every to_plot() | Mixed concerns | MEDIUM |
| **hv.extension("bokeh", "plotly")** | Module-level initialization | Global state | LOW |

---

## 2. Proposed Decoupled Architecture

### 2.1 Design Principles

1. **Separation of Concerns:** Data representation vs. visualization rendering
2. **Plugin Architecture:** Visualization backends register as plugins
3. **Minimal Core:** Keep only data + metadata in core
4. **Adapter Pattern:** Translate data formats for different renderers
5. **Backward Compatibility:** Maintain existing API during transition

### 2.2 New Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  bencher-core (minimal dependencies)                        │
├─────────────────────────────────────────────────────────────┤
│  Bench, BenchRunner, BenchCfg                               │
│  ParametrizedSweep, InputVars                               │
│  ResultMetadata (NEW)                                       │
│  BenchResultData (NEW - data-only, no viz)                  │
│    ├── xr.Dataset storage                                   │
│    ├── Data aggregation/reduction                           │
│    ├── to_pandas(), to_xarray(), to_dict()                  │
│    └── No visualization methods                             │
│  VisualizationRegistry (NEW)                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
         Adapter Interface (protocol/ABC)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  bencher-viz-holoviews (separate repo)                      │
├─────────────────────────────────────────────────────────────┤
│  HoloviewsAdapter                                            │
│  HoloviewsRenderer                                           │
│  Plot type implementations                                   │
│    ├── ScatterPlot, LinePlot, BarPlot                       │
│    ├── HeatmapPlot, SurfacePlot                             │
│    └── DistributionPlots (Box, Violin, Jitter)              │
│  ComposableLayout (Panel-based)                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  bencher-viz-plotly (future, separate repo)                 │
├─────────────────────────────────────────────────────────────┤
│  PlotlyAdapter                                               │
│  PlotlyRenderer                                              │
│  Plot implementations in pure Plotly                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  bencher-viz-matplotlib (future, separate repo)             │
├─────────────────────────────────────────────────────────────┤
│  MatplotlibAdapter                                           │
│  Static plot generation for publications                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Core Components

#### 2.3.1 BenchResultData (replaces BenchResultBase)

**Location:** `bencher/results/bench_result_data.py`

**Responsibilities:**
- Store xarray.Dataset
- Data aggregation and reduction (ReduceType operations)
- Conversions: to_pandas(), to_xarray(), to_dict(), to_json()
- Metadata management
- **NO** visualization or UI rendering

```python
# bencher/results/bench_result_data.py
from dataclasses import dataclass
import xarray as xr
import pandas as pd
from typing import Optional, List, Any, Dict

@dataclass
class ResultMetadata:
    """Metadata about benchmark results - no visualization info"""
    bench_name: str
    input_vars: List[str]
    result_vars: List[str]
    dimensions: Dict[str, int]
    units: Dict[str, str]
    timestamp: datetime
    # Configuration needed for data operations only
    repeats: int
    over_time: bool

class BenchResultData:
    """Pure data container with no visualization dependencies"""

    def __init__(self, metadata: ResultMetadata) -> None:
        self.metadata = metadata
        self.ds = xr.Dataset()
        self.object_references = []  # For non-array data
        self.datasets = []  # For ResultDataSet types

    # Data access methods
    def to_xarray(self) -> xr.Dataset:
        """Return underlying xarray dataset"""
        return self.ds

    def to_pandas(self, flatten: bool = False) -> pd.DataFrame:
        """Convert to pandas DataFrame"""
        # Implementation

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary format"""
        # Implementation

    def to_json(self, path: Optional[str] = None) -> str:
        """Export to JSON"""
        # Implementation

    # Data operations (no visualization)
    def reduce(self, reduce_type: ReduceType) -> xr.Dataset:
        """Apply reduction operations (mean, std, squeeze, etc.)"""
        # Implementation moved from BenchResultBase

    def aggregate(self, dims: List[str], agg_fn: str = "mean") -> xr.Dataset:
        """Aggregate over specified dimensions"""
        # Implementation

    def filter_dims(self, **dim_filters) -> 'BenchResultData':
        """Filter dataset by dimension values"""
        # Implementation

    def slice_by_coord(self, coord: str, value: Any) -> 'BenchResultData':
        """Slice dataset by coordinate value"""
        # Implementation
```

#### 2.3.2 VisualizationRegistry (Plugin System)

**Location:** `bencher/visualization/registry.py`

```python
# bencher/visualization/registry.py
from typing import Protocol, Dict, Type, Any, Optional, List
from abc import ABC, abstractmethod

class VisualizationAdapter(Protocol):
    """Protocol for visualization backends"""

    @staticmethod
    def name() -> str:
        """Backend identifier (e.g., 'holoviews', 'plotly', 'matplotlib')"""
        ...

    @staticmethod
    def supported_plot_types() -> List[str]:
        """Return list of supported plot types"""
        ...

    def render(
        self,
        result_data: 'BenchResultData',
        plot_type: str,
        **kwargs
    ) -> Any:
        """Render a specific plot type"""
        ...

    def auto_plot(
        self,
        result_data: 'BenchResultData',
        plot_types: Optional[List[str]] = None,
        **kwargs
    ) -> Any:
        """Automatically generate suitable plots"""
        ...

    def compose_layout(
        self,
        plots: List[Any],
        layout_type: str = "column"
    ) -> Any:
        """Compose multiple plots into layout"""
        ...


class VisualizationRegistry:
    """Global registry for visualization backends"""

    _adapters: Dict[str, Type[VisualizationAdapter]] = {}
    _default_adapter: Optional[str] = None

    @classmethod
    def register(cls, adapter_class: Type[VisualizationAdapter]) -> None:
        """Register a visualization adapter"""
        name = adapter_class.name()
        cls._adapters[name] = adapter_class
        if cls._default_adapter is None:
            cls._default_adapter = name

    @classmethod
    def get_adapter(cls, name: Optional[str] = None) -> VisualizationAdapter:
        """Get adapter instance by name (or default)"""
        adapter_name = name or cls._default_adapter
        if adapter_name not in cls._adapters:
            raise ValueError(f"Adapter '{adapter_name}' not registered")
        return cls._adapters[adapter_name]()

    @classmethod
    def list_adapters(cls) -> List[str]:
        """List all registered adapters"""
        return list(cls._adapters.keys())

    @classmethod
    def set_default(cls, name: str) -> None:
        """Set default visualization backend"""
        if name not in cls._adapters:
            raise ValueError(f"Adapter '{name}' not registered")
        cls._default_adapter = name
```

#### 2.3.3 BenchResult (New Facade)

**Location:** `bencher/results/bench_result.py`

```python
# bencher/results/bench_result.py
from typing import Optional, Any, List
from bencher.results.bench_result_data import BenchResultData, ResultMetadata
from bencher.visualization.registry import VisualizationRegistry

class BenchResult:
    """Facade for results with optional visualization"""

    def __init__(self, metadata: ResultMetadata) -> None:
        self.data = BenchResultData(metadata)
        self._viz_backend: Optional[str] = None

    # Data access (delegates to BenchResultData)
    def to_xarray(self):
        return self.data.to_xarray()

    def to_pandas(self, flatten=False):
        return self.data.to_pandas(flatten)

    def to_dict(self):
        return self.data.to_dict()

    # Visualization methods (uses registry)
    def use_backend(self, backend: str) -> 'BenchResult':
        """Switch visualization backend"""
        self._viz_backend = backend
        return self

    def plot(
        self,
        plot_type: str,
        backend: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Generate a specific plot type"""
        backend = backend or self._viz_backend
        adapter = VisualizationRegistry.get_adapter(backend)
        return adapter.render(self.data, plot_type, **kwargs)

    def auto_plot(
        self,
        plot_types: Optional[List[str]] = None,
        backend: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Automatically generate suitable plots"""
        backend = backend or self._viz_backend
        adapter = VisualizationRegistry.get_adapter(backend)
        return adapter.auto_plot(self.data, plot_types, **kwargs)

    # Backward compatibility (delegates to default backend)
    def to_scatter(self, **kwargs):
        """Legacy API - delegates to visualization backend"""
        return self.plot("scatter", **kwargs)

    def to_line(self, **kwargs):
        """Legacy API - delegates to visualization backend"""
        return self.plot("line", **kwargs)

    def to_auto(self, **kwargs):
        """Legacy API - delegates to auto_plot"""
        return self.auto_plot(**kwargs)
```

### 2.4 Visualization Plugin Structure

#### Example: bencher-viz-holoviews package

```
bencher-viz-holoviews/
├── pyproject.toml
├── README.md
├── bencher_viz_holoviews/
│   ├── __init__.py
│   ├── adapter.py              # HoloviewsAdapter implementation
│   ├── renderer.py             # Core rendering logic
│   ├── layout.py               # ComposableLayout with Panel
│   ├── plot_filter.py          # PlotFilter logic
│   ├── plots/
│   │   ├── scatter.py
│   │   ├── line.py
│   │   ├── bar.py
│   │   ├── heatmap.py
│   │   ├── surface.py
│   │   ├── distribution/
│   │   │   ├── box_whisker.py
│   │   │   ├── violin.py
│   │   │   └── scatter_jitter.py
│   │   └── video.py
│   └── utils.py
└── tests/
```

**Key Implementation:** `adapter.py`

```python
# bencher-viz-holoviews/bencher_viz_holoviews/adapter.py
import panel as pn
import holoviews as hv
import hvplot.xarray
from bencher.visualization.registry import VisualizationAdapter, VisualizationRegistry
from bencher.results.bench_result_data import BenchResultData
from typing import List, Any, Optional

hv.extension("bokeh", "plotly")

class HoloviewsAdapter:
    """Holoviews/Panel-based visualization adapter"""

    @staticmethod
    def name() -> str:
        return "holoviews"

    @staticmethod
    def supported_plot_types() -> List[str]:
        return [
            "scatter", "line", "bar", "curve", "heatmap", "surface",
            "box_whisker", "violin", "scatter_jitter",
            "histogram", "video_summary", "table"
        ]

    def render(
        self,
        result_data: BenchResultData,
        plot_type: str,
        **kwargs
    ) -> pn.panel:
        """Render specific plot type"""
        # Import plot type implementation
        from bencher_viz_holoviews.plots import get_plot_renderer

        renderer = get_plot_renderer(plot_type)

        # Convert BenchResultData to holoviews dataset
        hv_ds = self._to_hv_dataset(result_data, **kwargs)

        # Render using plot-specific logic
        return renderer(hv_ds, result_data.metadata, **kwargs)

    def auto_plot(
        self,
        result_data: BenchResultData,
        plot_types: Optional[List[str]] = None,
        **kwargs
    ) -> pn.Column:
        """Auto-generate suitable plots"""
        from bencher_viz_holoviews.plot_filter import PlotFilter
        from bencher_viz_holoviews.plots import DEFAULT_PLOT_CALLBACKS

        plot_callbacks = plot_types or DEFAULT_PLOT_CALLBACKS

        plots = pn.Column()
        for callback in plot_callbacks:
            # Apply filter to check suitability
            if PlotFilter.matches_result(result_data, callback):
                plot = self.render(result_data, callback, **kwargs)
                if plot is not None:
                    plots.append(plot)

        return plots

    def compose_layout(
        self,
        plots: List[Any],
        layout_type: str = "column"
    ) -> pn.panel:
        """Compose plots into Panel layout"""
        if layout_type == "column":
            return pn.Column(*plots)
        elif layout_type == "row":
            return pn.Row(*plots)
        elif layout_type == "grid":
            return pn.GridSpec(*plots)
        else:
            raise ValueError(f"Unknown layout type: {layout_type}")

    def _to_hv_dataset(
        self,
        result_data: BenchResultData,
        reduce: Optional[str] = None,
        **kwargs
    ) -> hv.Dataset:
        """Convert BenchResultData to HoloViews Dataset"""
        # Apply reduction if needed
        if reduce:
            ds = result_data.reduce(reduce)
        else:
            ds = result_data.to_xarray()

        # Convert to holoviews
        return hv.Dataset(ds)


# Auto-register when imported
VisualizationRegistry.register(HoloviewsAdapter)
```

---

## 3. Migration Strategy

### 3.1 Phase 1: Core Refactoring (Breaking Changes)

**Goal:** Separate data from visualization in core

**Changes:**
1. Create `BenchResultData` class (data-only)
2. Create `ResultMetadata` dataclass
3. Create `VisualizationRegistry` system
4. Refactor `BenchResult` to use facade pattern
5. Move visualization logic to `bencher/visualization/` (temporary location)

**Impact:**
- BenchResultBase → BenchResultData (rename + remove viz methods)
- Remove multiple inheritance from BenchResult
- Bench/BenchRunner updated to create ResultMetadata

**Timeline:** 2-3 weeks

### 3.2 Phase 2: Extract Holoviews Plugin

**Goal:** Move holoviews viz to separate package

**Changes:**
1. Create `bencher-viz-holoviews` package
2. Implement `HoloviewsAdapter`
3. Move all holoview result classes to plugin
4. Move ComposableContainer to plugin
5. Move PlotFilter to plugin
6. Add plugin auto-discovery

**Impact:**
- New dependency: `bencher-viz-holoviews`
- Core bencher no longer requires holoviews, hvplot, panel directly
- Visualization still works via adapter pattern

**Timeline:** 3-4 weeks

### 3.3 Phase 3: Backward Compatibility Layer

**Goal:** Maintain existing API for users

**Changes:**
1. Keep legacy methods in BenchResult (delegate to adapter)
2. Add deprecation warnings
3. Update documentation with migration guide
4. Provide examples of new API

**Impact:**
- Existing code continues working
- Users encouraged to migrate to new API
- Clear migration path documented

**Timeline:** 1-2 weeks

### 3.4 Phase 4: Additional Backends (Optional)

**Goal:** Demonstrate plugin flexibility

**Changes:**
1. Create `bencher-viz-plotly` package (pure Plotly, no Panel)
2. Create `bencher-viz-matplotlib` package (static plots)
3. Document plugin development guide

**Timeline:** 2-3 weeks each

---

## 4. Benefits

### 4.1 Modularity
- **Separate repositories** for different viz backends
- Core bencher becomes lightweight
- Easier to maintain and version independently

### 4.2 Flexibility
- Users choose visualization backend via config
- Easy to add new backends (plotly, matplotlib, altair, etc.)
- Can mix backends in same project

### 4.3 Testing
- Core data logic tested without viz dependencies
- Viz plugins tested independently
- Mocking becomes easier

### 4.4 Performance
- Optional viz dependencies (lighter installs)
- Can use lightweight backends for CI/CD
- Core operations faster without viz overhead

### 4.5 Community Contributions
- External developers can create viz plugins
- No need to fork core repository
- Plugin ecosystem can grow independently

---

## 5. Risks & Mitigation

### 5.1 Risk: Breaking Changes for Users

**Mitigation:**
- Maintain backward compatibility layer (Phase 3)
- Provide comprehensive migration guide
- Use semantic versioning (v2.0.0 for breaking changes)
- Gradual deprecation warnings

### 5.2 Risk: Complexity Increase

**Mitigation:**
- Clear documentation of plugin system
- Provide template for new adapters
- Keep default behavior simple (auto-register holoviews)
- Examples for common use cases

### 5.3 Risk: Performance Overhead

**Mitigation:**
- Adapter pattern adds minimal overhead
- Benchmark before/after refactor
- Optimize hot paths if needed
- Cache adapter instances

### 5.4 Risk: xarray Coupling Remains

**Mitigation:**
- Accept xarray as core data structure (widely used)
- Future: Add DataAdapter pattern for alternative structures
- For now: Focus on decoupling visualization

---

## 6. Example Usage

### 6.1 Current API (Before)

```python
from bencher import Bench

bench = Bench(...)
result = bench.run_sweep()

# Visualization tightly coupled
result.to_auto_plots()
result.to_scatter()
result.to_line()
```

### 6.2 New API (After)

```python
from bencher import Bench
from bencher.visualization import VisualizationRegistry

# Holoviews auto-registered on import
import bencher_viz_holoviews

bench = Bench(...)
result = bench.run_sweep()

# Same as before - backward compatible
result.auto_plot()
result.plot("scatter")
result.plot("line")

# Or explicitly choose backend
result.use_backend("holoviews").auto_plot()

# Switch backends easily
import bencher_viz_plotly
result.use_backend("plotly").plot("scatter")

# Mix backends
hv_plot = result.plot("heatmap", backend="holoviews")
plotly_plot = result.plot("surface", backend="plotly")

# Data access unchanged
df = result.to_pandas()
ds = result.to_xarray()
```

### 6.3 Plugin Development

```python
# Creating custom adapter
from bencher.visualization import VisualizationAdapter, VisualizationRegistry

class MyCustomAdapter:
    @staticmethod
    def name() -> str:
        return "mycustom"

    @staticmethod
    def supported_plot_types() -> List[str]:
        return ["scatter", "line"]

    def render(self, result_data, plot_type, **kwargs):
        # Custom rendering logic
        pass

# Register adapter
VisualizationRegistry.register(MyCustomAdapter)

# Use it
result.use_backend("mycustom").plot("scatter")
```

---

## 7. Dependencies After Refactor

### Core Package (bencher)

```toml
# pyproject.toml
[project]
name = "bencher"
dependencies = [
    "xarray>=2024.0.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "param>=2.0.0",
    "diskcache>=5.6.0",
    # NO holoviews, panel, hvplot, plotly
]

[project.optional-dependencies]
viz-holoviews = ["bencher-viz-holoviews>=1.0.0"]
viz-plotly = ["bencher-viz-plotly>=1.0.0"]
viz-matplotlib = ["bencher-viz-matplotlib>=1.0.0"]
all = [
    "bencher-viz-holoviews>=1.0.0",
    "bencher-viz-plotly>=1.0.0",
]
```

### Visualization Plugin (bencher-viz-holoviews)

```toml
# bencher-viz-holoviews/pyproject.toml
[project]
name = "bencher-viz-holoviews"
dependencies = [
    "bencher>=2.0.0",  # Core with adapter interface
    "holoviews>=1.18.0",
    "hvplot>=0.9.0",
    "panel>=1.3.0",
    "bokeh>=3.3.0",
]

[project.optional-dependencies]
plotly = ["plotly>=5.18.0"]
```

---

## 8. Action Items Summary

### Immediate (Research Phase)
- [x] Analyze current architecture
- [x] Identify coupling points
- [ ] Review with team/maintainer
- [ ] Prioritize compatibility requirements
- [ ] Define acceptance criteria

### Short Term (Phase 1)
- [ ] Create `BenchResultData` class
- [ ] Implement `VisualizationRegistry`
- [ ] Refactor `BenchResult` facade
- [ ] Update Bench/BenchRunner
- [ ] Write unit tests for core data layer
- [ ] Update documentation

### Medium Term (Phase 2)
- [ ] Create `bencher-viz-holoviews` package structure
- [ ] Implement `HoloviewsAdapter`
- [ ] Migrate all plot classes
- [ ] Migrate ComposableContainer
- [ ] Migrate PlotFilter
- [ ] Integration tests for plugin

### Long Term (Phase 3+)
- [ ] Backward compatibility layer
- [ ] Migration guide documentation
- [ ] Example gallery with new API
- [ ] (Optional) Create additional adapters
- [ ] Community plugin development guide

---

## 9. Recommendations

### Priority: HIGH
1. **Start with Phase 1** - Core refactoring provides immediate benefits
2. **Maintain xarray** - Don't try to abstract data structure yet
3. **Focus on adapter pattern** - Most flexible for future extensions

### Priority: MEDIUM
4. **Keep Panel in first plugin** - Don't try to abstract layout immediately
5. **Document extensively** - Plugin system needs clear docs
6. **Add integration tests** - Ensure plugins work with core

### Priority: LOW
7. **Alternative backends** - Wait for community demand
8. **Data structure abstraction** - Only if needed later
9. **Advanced plugin features** - Start simple, extend later

### Quick Wins
- Separate PlotFilter into plugin (low hanging fruit)
- Extract ComposableContainer (already well-abstracted)
- Move hvplot imports to plugin (reduce core deps)

### Don't
- Don't abstract xarray (too central, no clear benefit)
- Don't support Python < 3.9 (use modern features)
- Don't break backward compat without migration path

---

## 10. Conclusion

This proposal provides a pragmatic path to decouple visualization from core benchmarking functionality. The adapter pattern with plugin registry enables:

1. **Separation of concerns** - Data vs. rendering
2. **Independent repositories** - Core + plugins
3. **Backward compatibility** - Existing code works
4. **Extensibility** - Easy to add new backends
5. **Lighter core** - Optional visualization dependencies

**Estimated Total Effort:** 8-12 weeks for Phases 1-3

**Recommended Next Steps:**
1. Review this proposal with team
2. Create proof-of-concept branch with simplified adapter
3. Test backward compatibility with existing examples
4. Iterate on design based on feedback
5. Begin Phase 1 implementation

---

**Questions? Feedback?**

This is a living document. Please provide feedback on:
- Missing requirements
- Alternative approaches
- Priority of phases
- Compatibility concerns
- Plugin API design
