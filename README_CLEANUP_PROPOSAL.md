# Results Visualization Cleanup - Investigation Summary

## Overview

This investigation proposes a strategy to decouple the results visualization code from the core bencher framework, enabling visualization code to live in a separate repository while maintaining backward compatibility.

## Documents Created

1. **RESULTS_VISUALIZATION_CLEANUP_PROPOSAL.md** (Main Proposal)
   - Comprehensive analysis of current architecture
   - Detailed decoupled architecture design
   - Migration strategy with 3 phases
   - Benefits, risks, and mitigation strategies
   - Code examples and usage patterns

2. **REFACTORING_QUICK_REFERENCE.md** (Quick Reference)
   - TL;DR summary of the proposal
   - Side-by-side comparison of current vs. proposed architecture
   - Key components and their responsibilities
   - Migration checklist
   - Quick reference for developers

3. **ARCHITECTURE_DIAGRAM.md** (Visual Guide)
   - ASCII diagrams of current and proposed architectures
   - Dependency graphs
   - Data flow diagrams
   - Directory structure comparison
   - Plugin registration flow

4. **poc_adapter_interface.py** (Proof of Concept)
   - Working code demonstrating the adapter pattern
   - Shows how plugins would register and be used
   - Demonstrates backward compatibility
   - Can be run with: `python poc_adapter_interface.py`

## Key Findings

### Current Issues

1. **Tight Coupling**: BenchResult uses multiple inheritance from 14+ visualization classes
2. **Mixed Concerns**: BenchResultBase (753 lines) mixes data storage with UI rendering
3. **Heavy Dependencies**: Core requires holoviews, hvplot, panel, plotly even for data-only usage
4. **Inflexibility**: Cannot add new visualization backends without modifying core
5. **Maintenance Burden**: Single monolithic codebase for data + all visualizations

### Proposed Solution

**Visualization Adapter Pattern** with plugin-based architecture:

- **BenchResultData**: Pure data container (replaces BenchResultBase)
- **VisualizationRegistry**: Plugin system for registering visualization backends
- **VisualizationAdapter**: Protocol/interface that all plugins implement
- **BenchResult**: Facade that delegates to data + visualization adapters

### Key Benefits

✅ **Modularity**: Visualization code in separate repositories
✅ **Flexibility**: Easy to add new backends (matplotlib, plotly, altair)
✅ **Lighter Core**: Core has minimal dependencies (xarray, pandas only)
✅ **Better Testing**: Test data and visualization independently
✅ **Backward Compatible**: Existing code continues working
✅ **Community Friendly**: External developers can create visualization plugins

### Migration Strategy

**Phase 1: Core Refactoring** (3 weeks)
- Create BenchResultData (data-only class)
- Create VisualizationRegistry (plugin system)
- Refactor BenchResult to facade pattern
- Keep viz code in core temporarily

**Phase 2: Extract Plugin** (4 weeks)
- Create bencher-viz-holoviews package (separate repo)
- Move all holoview result classes to plugin
- Move ComposableContainer to plugin
- Auto-register adapter on import

**Phase 3: Compatibility** (2 weeks)
- Add backward compatibility layer
- Legacy methods delegate to adapters
- Documentation and migration guide

**Total Estimated Time**: 8-12 weeks

## Example API

### Current (Still Works)

```python
result = bench.run_sweep()
result.to_scatter()
result.to_line()
result.to_auto_plots()
```

### New (Recommended)

```python
# Auto-uses default backend
result.plot("scatter")
result.auto_plot()

# Explicit backend selection
result.use_backend("holoviews").auto_plot()

# Switch backends easily
import bencher_viz_plotly
result.use_backend("plotly").plot("surface")

# Data access unchanged
df = result.to_pandas()
ds = result.to_xarray()
```

## Critical Coupling Points Identified

### HIGH Priority (Must Decouple)

1. ✅ **BenchResultBase methods returning pn.Column/pn.Row**
   - Solution: Move to adapter, return adapter-specific types

2. ✅ **Multiple inheritance in BenchResult**
   - Solution: Replace with facade pattern + delegation

3. ✅ **HoloviewResult.to_hv_dataset() throughout**
   - Solution: Move conversion logic to adapter

4. ✅ **Recursive layout composition hardcoded to Panel**
   - Solution: Move ComposableContainer to plugin

5. ✅ **PlotFilter validation in every to_plot()**
   - Solution: Move PlotFilter to plugin

### LOW Priority (Accept for Now)

6. ⚠️ **xarray.Dataset as core data structure**
   - Accept: Widely used, performant, well-maintained

7. ⚠️ **hv.extension() module-level initialization**
   - Accept: Move to plugin __init__

## Package Structure After Refactor

```
bencher-core/                    (THIS REPO)
├── pyproject.toml               (deps: xarray, pandas)
└── bencher/
    ├── bencher.py
    ├── results/
    │   ├── bench_result_data.py   (NEW - data only)
    │   └── bench_result.py        (REFACTORED - facade)
    └── visualization/
        ├── registry.py            (NEW - plugin system)
        └── adapter.py             (NEW - protocol)

bencher-viz-holoviews/           (NEW SEPARATE REPO)
├── pyproject.toml               (deps: bencher-core, holoviews, panel)
└── bencher_viz_holoviews/
    ├── adapter.py
    ├── plots/
    │   ├── scatter.py
    │   ├── line.py
    │   └── ...
    └── layout.py

bencher-viz-plotly/              (OPTIONAL FUTURE)
bencher-viz-matplotlib/          (OPTIONAL FUTURE)
```

## Dependencies After Refactor

### Core Package

```toml
# bencher-core/pyproject.toml
dependencies = [
    "xarray>=2024.0.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    # NO visualization libraries
]

[project.optional-dependencies]
viz = ["bencher-viz-holoviews>=1.0.0"]
```

### Visualization Plugin

```toml
# bencher-viz-holoviews/pyproject.toml
dependencies = [
    "bencher-core>=2.0.0",
    "holoviews>=1.18.0",
    "hvplot>=0.9.0",
    "panel>=1.3.0",
    "bokeh>=3.3.0",
]
```

## Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking changes | Backward compatibility layer + deprecation warnings |
| Increased complexity | Clear docs + plugin template + examples |
| Performance overhead | Minimal (adapter pattern is lightweight) |
| xarray still coupled | Accept as core data structure (widely used) |

## Recommendations

### DO

1. ✅ **Start with Phase 1** - Core refactoring provides immediate benefits
2. ✅ **Maintain xarray** - Don't try to abstract data structure yet
3. ✅ **Focus on adapter pattern** - Most flexible for future extensions
4. ✅ **Document extensively** - Plugin system needs clear documentation
5. ✅ **Add integration tests** - Ensure plugins work with core

### DON'T

1. ❌ **Don't abstract xarray** - Too central, no clear benefit
2. ❌ **Don't support Python < 3.9** - Use modern features
3. ❌ **Don't break backward compat** - Provide migration path
4. ❌ **Don't try to abstract Panel** - Keep it in first plugin

## Next Steps

1. **Review** these proposals with team/maintainers
2. **Discuss** priorities and timeline constraints
3. **Create** proof-of-concept branch with simplified adapter
4. **Test** with 2-3 existing examples to validate approach
5. **Iterate** on design based on feedback
6. **Begin** Phase 1 implementation if approved

## Questions to Discuss

- [ ] Is backward compatibility required? (Assumed: YES)
- [ ] Can we do major version bump? (Recommended: v2.0.0)
- [ ] Should we support multiple backends from day 1? (Recommended: Start with holoviews)
- [ ] Do we need to abstract xarray? (Recommended: NO)
- [ ] What are timeline constraints? (Estimated: 8-12 weeks)
- [ ] Should visualization plugins be in bencher org or separate?
- [ ] What's the plan for maintaining backward compatibility long-term?

## Files Summary

| File | Purpose | Lines |
|------|---------|-------|
| RESULTS_VISUALIZATION_CLEANUP_PROPOSAL.md | Full detailed proposal | ~1000 |
| REFACTORING_QUICK_REFERENCE.md | Quick reference guide | ~400 |
| ARCHITECTURE_DIAGRAM.md | Visual architecture diagrams | ~600 |
| poc_adapter_interface.py | Working proof of concept | ~600 |
| README_CLEANUP_PROPOSAL.md | This summary document | ~250 |

## Contact

For questions or feedback on this proposal, please discuss with the bencher maintainer team.

---

**Status**: ✅ Investigation Complete - Awaiting Review

**Date**: 2025-11-07

**Investigator**: Claude (Anthropic AI)
