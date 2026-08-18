"""Benchmark configuration, split into composable sub-config groups.

Each sub-config is a plain ``param.Parameterized``; :class:`BenchRunCfg`
composes them via ``param.ClassSelector`` slots and :class:`BenchCfg` adds the
sweep metadata. There is exactly one canonical way to reach every parameter —
the grouped attribute path (``run_cfg.cache.results``,
``run_cfg.execution.repeats``, ...).
"""

from bencher.bench_cfg.bench_cfg_class import BenchCfg
from bencher.bench_cfg.cache_cfg import CacheCfg
from bencher.bench_cfg.dims_cfg import DimsCfg
from bencher.bench_cfg.display_cfg import DisplayCfg
from bencher.bench_cfg.execution_cfg import ExecutionCfg
from bencher.bench_cfg.regression_cfg import RegressionCfg
from bencher.bench_cfg.run_cfg import BenchRunCfg
from bencher.bench_cfg.server_cfg import ServerCfg, ShowMode, normalize_show
from bencher.bench_cfg.time_cfg import TimeCfg
from bencher.bench_cfg.visualization_cfg import VisualizationCfg

__all__ = [
    "BenchCfg",
    "BenchRunCfg",
    "CacheCfg",
    "DimsCfg",
    "DisplayCfg",
    "ExecutionCfg",
    "RegressionCfg",
    "ServerCfg",
    "ShowMode",
    "TimeCfg",
    "VisualizationCfg",
    "normalize_show",
]
