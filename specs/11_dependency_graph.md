# 11 - Module Architecture

> Per-module import lists go stale quickly. Use `grep "from bencher" <file>` to check current imports. This document captures the **layered architecture** and **circular dependency resolution** that aren't obvious from scanning imports.

## Layered Architecture

```
┌─────────────────────────────────────────────┐
│          Orchestration Layer                 │
│   bencher.py, bench_runner.py,              │
│   bench_report.py, bench_plot_server.py     │
├─────────────────────────────────────────────┤
│          Execution Layer                     │
│   sweep_executor.py, result_collector.py,   │
│   worker_manager.py, worker_job.py, job.py  │
├─────────────────────────────────────────────┤
│          Results Layer                       │
│   bench_result.py, bench_result_base.py,    │
│   holoview_results/*, composable_container/*│
├─────────────────────────────────────────────┤
│          Configuration Layer                 │
│   bench_cfg.py, plt_cnt_cfg.py,            │
│   plot_filter.py                            │
├─────────────────────────────────────────────┤
│          Variables Layer                     │
│   parametrised_sweep.py, inputs.py,        │
│   results.py, time.py, sweep_base.py       │
├─────────────────────────────────────────────┤
│          Foundation Layer                    │
│   utils.py, sample_order.py, class_enum.py │
└─────────────────────────────────────────────┘
        ↕ (lazy imports)
   factories.py
```

Layers depend downward only, with one exception resolved via `factories.py`.

## Circular Dependency Analysis

### Primary Cycle
```
ParametrizedSweep → to_bench()/to_bench_runner()
  → factories.create_bench()/create_bench_runner()
    → Bench/BenchRunner → BenchCfg → uses ParametrizedSweep parameters
```

### Resolution: `factories.py`
Two techniques:
1. **`TYPE_CHECKING` guard** — compile-time only imports for type annotations
2. **Lazy imports inside function bodies** — `from bencher.bencher import Bench` at call time, not module load time

No other circular dependencies exist. `bench_cfg.py` imports `Executors` from `job.py` but `job.py` only imports from `utils.py`. `result_collector.py` imports from `bench_result.py` which imports result types that import from `bench_result_base.py` → `bench_cfg.py`, but `bench_cfg.py` does not import from results.

## Key External Dependencies

| Library | Primary Role |
|---------|-------------|
| `param` | All parameter definitions, config classes, sweep base |
| `xarray` | N-dimensional result storage |
| `holoviews` | Interactive plot generation |
| `panel` | Dashboard layouts, web serving, report generation |
| `plotly` | 3D plots (volume, surface) |
| `diskcache` | Persistent caching (sample + benchmark levels) |
| `optuna` | Hyperparameter optimization |
| `moviepy` / `PIL` | Video generation |
