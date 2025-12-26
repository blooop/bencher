"""Backward compatibility layer for benchmark configuration.

This module re-exports classes from the bench_cfg package to maintain
backward compatibility with existing code that imports from bencher.bench_cfg.

For new code, consider importing directly from the focused submodules:
    from bencher.bench_cfg.cache_cfg import CacheCfg
    from bencher.bench_cfg.execution_cfg import ExecutionCfg
    etc.
"""

from bencher.bench_cfg import (
    BenchPlotSrvCfg,
    CacheCfg,
    ExecutionCfg,
    DisplayCfg,
    VisualizationCfg,
    TimeCfg,
    BenchRunCfg,
    BenchCfg,
    DimsCfg,
)

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
