"""Benchmark configuration package.

Configuration classes for benchmarking, organized by concern:

- CacheCfg: Caching (cache_results, cache_samples, only_plot, ...)
- ExecutionCfg: Execution (repeats, level, executor, nightly, headless)
- DisplayCfg: Output (print_bench_inputs, serve_pandas, ...)
- VisualizationCfg: Plotting (auto_plot, plot_size, use_holoview, ...)
- TimeCfg: History (over_time, run_tag, run_date, ...)
- BenchPlotSrvCfg: Server (port, show, allow_ws_origin)
- BenchRunCfg: Composes all above with backward-compatible flat access
- BenchCfg: Full benchmark config with variables and metadata
- DimsCfg: Dimension info extraction

Usage:
    # Flat access (backward compatible)
    cfg = BenchRunCfg(cache_results=True, repeats=5)
    cfg.auto_plot = False

    # Grouped access
    cfg.cache.cache_samples = True
    cfg.execution.level = 3
"""

from bencher.bench_cfg.server_cfg import BenchPlotSrvCfg
from bencher.bench_cfg.cache_cfg import CacheCfg
from bencher.bench_cfg.execution_cfg import ExecutionCfg
from bencher.bench_cfg.display_cfg import DisplayCfg
from bencher.bench_cfg.visualization_cfg import VisualizationCfg
from bencher.bench_cfg.time_cfg import TimeCfg
from bencher.bench_cfg.run_cfg import BenchRunCfg
from bencher.bench_cfg.bench_cfg_class import BenchCfg
from bencher.bench_cfg.dims_cfg import DimsCfg

__all__ = [
    "BenchPlotSrvCfg",
    "CacheCfg",
    "ExecutionCfg",
    "DisplayCfg",
    "VisualizationCfg",
    "TimeCfg",
    "BenchRunCfg",
    "BenchCfg",
    "DimsCfg",
]
