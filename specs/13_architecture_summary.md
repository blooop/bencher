# 13 - Architecture Summary

## High-Level Architecture

```
User API:  ParametrizedSweep → Bench → BenchRunner
                                 ↓
Config:    BenchPlotSrvCfg → BenchRunCfg → BenchCfg → DimsCfg
                                 ↓
Execution: WorkerManager + SweepExecutor + ResultCollector
           WorkerJob → Job → FutureCache → [Sample Cache]
                                             ↓
Results:   BenchResult (15-class MI) → PltCntCfg + PlotFilter → auto-selected plots
                                             ↓
Output:    Panel layout / BenchReport (HTML) / BenchPlotServer / GitHub Pages
                                             ↓
Integrations: Optuna (optimization) | Rerun (3D viz) | VideoWriter (moviepy)
```

## Key Architectural Patterns

### 1. Multiple Inheritance (Mixin Pattern)
`BenchResult` inherits from 15 parent classes, each providing a specific `to_*()` visualization method. Works because each parent provides non-overlapping methods and `BenchResultBase` is the shared root with common state.

### 2. Factory Pattern (Circular Dependency Break)
`factories.py` uses lazy imports to break: `ParametrizedSweep → Bench → BenchCfg → ParametrizedSweep`. Enables convenience methods `to_bench()` and `to_bench_runner()`.

### 3. Delegation Pattern
`Bench` delegates to `WorkerManager` (function wrapping), `SweepExecutor` (variable conversion, cache init), and `ResultCollector` (dataset creation, result storage).

### 4. Hash-Based Two-Tier Caching
- **Sample cache**: per-function-call results keyed by sorted input hash
- **Benchmark cache**: complete BenchResult keyed by BenchCfg hash
- `hash_persistent()` avoids PYTHONHASHSEED randomization; custom `__bencher_hash__` protocol for user types

### 5. N-Dimensional Data Model
Results stored as `xarray.Dataset` with dimensions matching the Cartesian product of inputs. Enables: automatic slicing, natural mapping to plot types (1D→line, 2D→heatmap, 3D→volume), level-based subsampling.

### 6. Automatic Plot Deduction
`PltCntCfg` classifies inputs as float/categorical, `PlotFilter` specifies valid ranges per plot type, all matching plots included (additive). Users can override via `plot_callbacks`.

## Design Trade-offs

| Choice | Rationale | Cost |
|--------|-----------|------|
| MI for BenchResult | Flat API, no delegation overhead | Complex MRO, hard init chains |
| diskcache persistence | Results survive across sessions, two-tier reuse | Serialization overhead, invalidation complexity |
| `param` library | Metadata (bounds, units), Panel/HoloViews integration | Learning curve, descriptor magic |
| Auto plot selection | Users don't need to know plot types | Sometimes suboptimal; must understand PlotFilter to customize |
| Full Cartesian product | Complete parameter space coverage | Exponential scaling (mitigated by caching + levels) |

## Technical Debt / Complexity Areas

1. **BenchResult 15-class MI** — hard to reason about. Consider composition or registry pattern.
2. **BenchRunCfg 40+ parameters** — many rarely used. Could benefit from parameter groups.
3. **bench_result_base.py 753 lines** — handles too many concerns (conversion, reduction, optimization, filtering, layout).
4. **12 result types with overlap** — ResultPath vs ResultImage vs ResultVideo are all filenames.
5. **SCOOP executor** — vestigial (commented out but in enum). Should remove or implement.
6. **Legacy CachedParams** (`caching.py`) — duplicates FutureCache functionality.
7. **PlotFilter negative bounds** — `cat_range: -1-0` semantics are unclear.
