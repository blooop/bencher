# 04 - Class Hierarchy

> Detailed class listings go stale quickly. Use `grep -r "^class "` to discover current classes. This document captures **architectural patterns** that aren't obvious from scanning source.

## BenchResult: 15-Class Multiple Inheritance

`BenchResult` (`bencher/results/bench_result.py:30-46`) is the most architecturally significant class. It inherits from **15 parent classes**:

```python
class BenchResult(
    VolumeResult,          # 3D volume plots
    BoxWhiskerResult,      # Box-whisker distribution
    ViolinResult,          # Violin distribution
    ScatterJitterResult,   # Jittered scatter distribution
    ScatterResult,         # 2D scatter
    LineResult,            # Line plots with tap
    BarResult,             # Bar charts
    HeatmapResult,         # 2D heatmaps with tap
    CurveResult,           # Smooth curves
    SurfaceResult,         # 3D surfaces
    HoloviewResult,        # HoloViews base
    HistogramResult,       # Histograms
    VideoSummaryResult,    # Video grid summaries
    DataSetResult,         # Raw dataset panels
    OptunaResult,          # Optuna optimization
):
```

**Why**: Acts as a mixin aggregator so any result can access any visualization method (`result.to_scatter()`, `result.to_heatmap()`, etc.) without delegation/wrapping overhead. Each parent provides non-overlapping `to_*()` methods. Python's C3 MRO resolves method lookup.

**Caveat**: `__init__` explicitly calls `VolumeResult.__init__` and `HoloviewResult.__init__` rather than using `super()`, bypassing cooperative MI.

## Key Inheritance Chains

### Configuration
```
param.Parameterized → BenchPlotSrvCfg → BenchRunCfg → BenchCfg
                                          (bench_cfg.py)
```

### Visualization (longest chain)
```
BenchResultBase → VideoResult → HoloviewResult → DistributionResult → BoxWhiskerResult → BenchResult (via MI)
```

### Sweep Types (multiple inheritance diamonds)
- `IntSweep(param.Integer, SweepBase)` — numeric
- `FloatSweep(param.Number, SweepBase)` — numeric
- `SweepSelector(param.Selector, SweepBase)` — categorical base
  - `BoolSweep`, `StringSweep`, `EnumSweep`, `YamlSweep` extend SweepSelector

### Orchestration
```
BenchPlotServer → Bench          (bencher.py)
BenchPlotServer → BenchReport    (bench_report.py)
```

## Delegation Pattern in Bench

`Bench` delegates to three internal managers rather than handling everything directly:
- **WorkerManager** — function wrapping and validation
- **SweepExecutor** — variable conversion and cache initialization
- **ResultCollector** — dataset creation and result storage

## Factory Pattern: Circular Dependency Break

`factories.py` breaks the cycle `ParametrizedSweep → Bench → BenchCfg → ParametrizedSweep` using lazy imports inside function bodies. This enables the convenience methods `to_bench()` and `to_bench_runner()` on ParametrizedSweep.

## Approximate Scale

~81 classes and ~7 enums across the package (excluding examples). The results subsystem is the largest (~21 visualization classes + 5 composable container classes).
