from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

import param

from bencher.bench_cfg.cache_cfg import CacheCfg
from bencher.bench_cfg.display_cfg import DisplayCfg
from bencher.bench_cfg.execution_cfg import ExecutionCfg
from bencher.bench_cfg.regression_cfg import RegressionCfg
from bencher.bench_cfg.server_cfg import ServerCfg
from bencher.bench_cfg.time_cfg import TimeCfg
from bencher.bench_cfg.visualization_cfg import VisualizationCfg


class BenchRunCfg(param.Parameterized):
    """Configuration for a benchmark run, composed of grouped sub-configs.

    Every parameter lives on exactly one sub-config; the attribute path is the
    one canonical way to reach it (``run_cfg.cache.results``,
    ``run_cfg.execution.repeats``, ``run_cfg.time.over_time``, ...). There are
    no flat aliases.

    ``param.ClassSelector`` defaults to ``instantiate=True``, so declaring an
    instance as the parameter default gives every ``BenchRunCfg`` its own fresh
    copy of each sub-config.

    Usage::

        # Ad-hoc construction — assemble the groups you care about.
        run_cfg = bn.BenchRunCfg(
            execution=bn.ExecutionCfg(subsampling_divisions=4, repeats=3),
            cache=bn.CacheCfg(results=True, samples=True),
            time=bn.TimeCfg(over_time=True),
        )

        # Or mutate in place — parameters are live.
        run_cfg = bn.BenchRunCfg()
        run_cfg.cache.results = True
        run_cfg.time.over_time = True

    Attributes:
        server (ServerCfg): Panel server options
        execution (ExecutionCfg): How the benchmark function is run
        cache (CacheCfg): Benchmark- and sample-level cache behaviour
        display (DisplayCfg): Console output and served tables
        visualization (VisualizationCfg): Plotting options
        time (TimeCfg): Over-time tracking and history
        regression (RegressionCfg): Regression detection
        run_tag (str): Tag for isolating cached results
        run_date (datetime): Date the benchmark run was performed
    """

    server = param.ClassSelector(class_=ServerCfg, default=ServerCfg())
    execution = param.ClassSelector(class_=ExecutionCfg, default=ExecutionCfg())
    cache = param.ClassSelector(class_=CacheCfg, default=CacheCfg())
    display = param.ClassSelector(class_=DisplayCfg, default=DisplayCfg())
    visualization = param.ClassSelector(class_=VisualizationCfg, default=VisualizationCfg())
    time = param.ClassSelector(class_=TimeCfg, default=TimeCfg())
    regression = param.ClassSelector(class_=RegressionCfg, default=RegressionCfg())

    run_tag: str = param.String(
        default="",
        doc="Define a tag for a run to isolate the results stored in the cache from other runs",
    )

    run_date: datetime = param.Date(
        default=None,
        doc="The date the bench run was performed",
    )

    def __init__(self, **params: Any) -> None:
        """Initialize BenchRunCfg with current datetime if not provided."""
        if "run_date" not in params:
            params["run_date"] = datetime.now()
        super().__init__(**params)

    def deep(self) -> BenchRunCfg:
        return deepcopy(self)
