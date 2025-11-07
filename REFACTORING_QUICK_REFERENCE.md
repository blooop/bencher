# Results Visualization Refactoring - Quick Reference

**Goal:** Enable visualization code to live in a separate repository

## TL;DR

**Current Problem:**
- BenchResult uses multiple inheritance from 14+ visualization classes
- Panel, HoloViews, hvplot hardcoded throughout
- Cannot separate viz code without breaking everything

**Proposed Solution:**
- Introduce **Visualization Adapter Pattern** with plugin registry
- Split into: `bencher-core` (data only) + `bencher-viz-holoviews` (viz plugin)
- Maintain backward compatibility

---

## Current vs. Proposed Architecture

### BEFORE (Current)

```
bencher/
  ├── bencher.py (Bench class)
  └── results/
      ├── bench_result_base.py       ← Data + Viz mixed (753 lines)
      ├── bench_result.py             ← Inherits from 14+ classes
      └── holoview_results/           ← Tightly coupled viz
          ├── scatter_result.py
          ├── line_result.py
          ├── bar_result.py
          └── ...

Dependencies in core:
  xarray, pandas, holoviews, hvplot, panel, plotly ← Too many!
```

### AFTER (Proposed)

```
bencher-core/
  ├── bencher.py (Bench class)
  ├── results/
  │   └── bench_result_data.py      ← Data only (no viz)
  └── visualization/
      └── registry.py                ← Plugin system

bencher-viz-holoviews/  (separate repo)
  └── bencher_viz_holoviews/
      ├── adapter.py                 ← Implements VisualizationAdapter
      ├── plots/
      │   ├── scatter.py
      │   ├── line.py
      │   └── ...
      └── layout.py

Dependencies in core:
  xarray, pandas ← Minimal!

Dependencies in viz plugin:
  bencher-core, holoviews, hvplot, panel ← Optional install
```

---

## Key Components

### 1. BenchResultData (replaces BenchResultBase)

**Location:** `bencher/results/bench_result_data.py`

**Purpose:** Pure data container with NO visualization

**Has:**
- xr.Dataset storage
- to_pandas(), to_xarray(), to_dict()
- reduce(), aggregate(), filter_dims()

**Does NOT have:**
- Any Panel imports
- Any HoloViews imports
- Any to_plot() methods
- Any layout composition

### 2. VisualizationRegistry

**Location:** `bencher/visualization/registry.py`

**Purpose:** Plugin system for visualization backends

**API:**
```python
# Register adapter
VisualizationRegistry.register(HoloviewsAdapter)

# Get adapter
adapter = VisualizationRegistry.get_adapter("holoviews")

# Use adapter
plot = adapter.render(result_data, "scatter")
```

### 3. VisualizationAdapter (Protocol)

**Purpose:** Interface that all visualization plugins must implement

**Required methods:**
- `name()` → str (e.g., "holoviews", "plotly")
- `supported_plot_types()` → List[str]
- `render(result_data, plot_type, **kwargs)` → plot object
- `auto_plot(result_data, **kwargs)` → composed plots
- `compose_layout(plots, layout_type)` → layout

### 4. BenchResult (New Facade)

**Location:** `bencher/results/bench_result.py`

**Purpose:** User-facing API that delegates to data + visualization

**Example:**
```python
result = bench.run_sweep()

# Data access (no viz dependency)
df = result.to_pandas()
ds = result.to_xarray()

# Visualization (uses plugin)
result.plot("scatter")          # Uses default backend
result.use_backend("holoviews").plot("line")
result.use_backend("plotly").plot("surface")
```

---

## Migration Path

### Phase 1: Core Refactoring (3 weeks)
- Create BenchResultData
- Create VisualizationRegistry
- Refactor BenchResult to facade pattern
- Keep viz code in core temporarily

### Phase 2: Extract Plugin (4 weeks)
- Create bencher-viz-holoviews package
- Move all holoview results to plugin
- Move ComposableContainer to plugin
- Auto-register on import

### Phase 3: Compatibility (2 weeks)
- Add backward compatibility layer
- Legacy methods delegate to adapter
- Documentation + migration guide

**Total Time:** 8-12 weeks

---

## Code Examples

### Current Code (Works as-is)

```python
from bencher import Bench

bench = Bench(...)
result = bench.run_sweep()

result.to_scatter()
result.to_line()
result.to_auto_plots()
```

### New Code (More Flexible)

```python
from bencher import Bench
import bencher_viz_holoviews  # Auto-registers

bench = Bench(...)
result = bench.run_sweep()

# Backward compatible
result.plot("scatter")
result.auto_plot()

# Or explicit backend selection
result.use_backend("holoviews").auto_plot()

# Switch backends
import bencher_viz_plotly
result.use_backend("plotly").plot("surface")
```

---

## High-Level Changes

### Files to Create

```
bencher/results/bench_result_data.py          (NEW - data only)
bencher/results/result_metadata.py            (NEW - metadata dataclass)
bencher/visualization/registry.py             (NEW - plugin system)
bencher/visualization/adapter.py              (NEW - protocol definition)
```

### Files to Modify

```
bencher/results/bench_result.py               (REFACTOR - becomes facade)
bencher/bencher.py                             (UPDATE - creates ResultMetadata)
bencher/bench_runner.py                        (UPDATE - uses new API)
```

### Files to Move to Plugin

```
bencher/results/bench_result_base.py          → Delete (split into data + viz)
bencher/results/holoview_results/*            → bencher-viz-holoviews/plots/
bencher/results/composable_container/*        → bencher-viz-holoviews/layout/
bencher/plotting/plot_filter.py               → bencher-viz-holoviews/
bencher/results/video_result.py               → bencher-viz-holoviews/
bencher/results/volume_result.py              → bencher-viz-holoviews/ (or plotly plugin)
```

---

## Dependency Changes

### Before

```toml
# pyproject.toml
dependencies = [
    "xarray",
    "pandas",
    "holoviews",    ← Required in core
    "hvplot",       ← Required in core
    "panel",        ← Required in core
    "plotly",       ← Required in core
    ...
]
```

### After

```toml
# bencher-core/pyproject.toml
dependencies = [
    "xarray",
    "pandas",
    # NO viz libraries!
]

[project.optional-dependencies]
viz = ["bencher-viz-holoviews>=1.0.0"]

# bencher-viz-holoviews/pyproject.toml
dependencies = [
    "bencher-core>=2.0.0",
    "holoviews",
    "hvplot",
    "panel",
    "plotly",
]
```

---

## Benefits Summary

✅ **Modularity** - Viz code in separate repo
✅ **Flexibility** - Easy to add new backends (matplotlib, altair, etc.)
✅ **Lighter core** - No heavy viz dependencies
✅ **Better testing** - Test data logic independently
✅ **Backward compatible** - Existing code keeps working
✅ **Community friendly** - External devs can create viz plugins

---

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking changes | Backward compatibility layer + deprecation warnings |
| Increased complexity | Clear docs + plugin template + examples |
| Performance overhead | Minimal (adapter pattern is lightweight) |
| xarray still coupled | Accept as core data structure (widely used) |

---

## Critical Coupling Points (From Analysis)

### HIGH PRIORITY to decouple:
1. ✅ **BenchResultBase methods returning pn.Column/pn.Row**
   - Solution: Move to adapter, return adapter-specific types

2. ✅ **Multiple inheritance in BenchResult**
   - Solution: Replace with facade pattern + delegation

3. ✅ **HoloviewResult.to_hv_dataset() calls throughout**
   - Solution: Move conversion logic to adapter

4. ✅ **Recursive layout composition hardcoded to Panel**
   - Solution: Move ComposableContainer to plugin

5. ✅ **PlotFilter validation in every to_plot()**
   - Solution: Move PlotFilter to plugin

### LOW PRIORITY (accept for now):
6. ⚠️ **xarray.Dataset as core data structure**
   - Accept: Widely used, performant, well-maintained

7. ⚠️ **hv.extension() module-level initialization**
   - Accept: Move to plugin __init__

---

## Next Steps

1. **Review this proposal** with maintainers
2. **Create PoC branch** with simplified adapter
3. **Test with 2-3 examples** to validate approach
4. **Iterate on design** based on feedback
5. **Begin Phase 1** if approved

---

## Questions to Answer

- [ ] Is backward compatibility required? (Assumed: YES)
- [ ] Can we do major version bump? (Recommended: 2.0.0)
- [ ] Should we support multiple backends from day 1? (Recommended: Start with holoviews only)
- [ ] Do we need to abstract xarray? (Recommended: NO, keep it)
- [ ] Timeline constraints? (Estimated: 8-12 weeks)

---

**Full Proposal:** See `RESULTS_VISUALIZATION_CLEANUP_PROPOSAL.md`
