from __future__ import annotations

import argparse
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

    @staticmethod
    def from_cmd_line(argv: list[str] | None = None) -> BenchRunCfg:
        """Create a BenchRunCfg by parsing command line arguments.

        Each sub-config registers its own flags via ``add_cli_args`` and
        consumes the parsed values back into an instance via
        ``apply_cli_args``, so flag ownership stays colocated with the
        parameters and the flat argparse namespace maps explicitly onto the
        nested slots.

        Args:
            argv: Argument list to parse. Defaults to ``sys.argv[1:]``.

        Returns:
            BenchRunCfg: Configuration object with settings from command line arguments
        """
        sub_cfgs = (
            ServerCfg,
            ExecutionCfg,
            CacheCfg,
            DisplayCfg,
            VisualizationCfg,
            TimeCfg,
            RegressionCfg,
        )
        parser = argparse.ArgumentParser(description="benchmark")
        for sub_cfg in sub_cfgs:
            sub_cfg.add_cli_args(parser)
        args = parser.parse_args(argv)
        return BenchRunCfg(
            server=ServerCfg.apply_cli_args(args),
            execution=ExecutionCfg.apply_cli_args(args),
            cache=CacheCfg.apply_cli_args(args),
            display=DisplayCfg.apply_cli_args(args),
            visualization=VisualizationCfg.apply_cli_args(args),
            time=TimeCfg.apply_cli_args(args),
            regression=RegressionCfg.apply_cli_args(args),
        )

    @classmethod
    def with_defaults(cls, run_cfg: BenchRunCfg | None = None, **defaults) -> BenchRunCfg:
        """Merge *defaults* into *run_cfg*, creating a new instance when needed.

        Defaults for grouped parameters are passed as plain dicts keyed by the
        sub-config slot name; top-level parameters (``run_tag``, ``run_date``)
        are passed directly::

            run_cfg = bn.BenchRunCfg.with_defaults(
                run_cfg,
                execution=dict(repeats=5, subsampling_divisions=4),
                cache=dict(results=True),
            )

        When *run_cfg* is ``None`` a fresh ``BenchRunCfg`` is created and the
        defaults applied to it. When *run_cfg* is provided, a deep copy is made
        and each default is applied only if the corresponding field is still at
        its param-level default value (i.e. the caller did not explicitly set
        it). The original *run_cfg* is never mutated. This lets benchmark
        functions declare sensible defaults while still allowing callers to
        override.

        Raises:
            ValueError: If any group name, top-level key, or key within a group
                is not a recognised parameter, or a group's defaults are not a
                dict.
        """
        params = cls.param.objects()
        group_slots = {
            name: p.class_ for name, p in params.items() if isinstance(p, param.ClassSelector)
        }
        unknown = set(defaults) - set(params)
        if unknown:
            raise ValueError(f"Unknown {cls.__name__} parameter(s): {', '.join(sorted(unknown))}")
        for group, values in defaults.items():
            if group in group_slots:
                if not isinstance(values, dict):
                    raise ValueError(
                        f"Defaults for the '{group}' group must be a dict, got {values!r}"
                    )
                unknown_keys = set(values) - set(group_slots[group].param)
                if unknown_keys:
                    raise ValueError(
                        f"Unknown {group_slots[group].__name__} parameter(s): "
                        f"{', '.join(sorted(unknown_keys))}"
                    )
        result = cls() if run_cfg is None else deepcopy(run_cfg)
        for key, value in defaults.items():
            if key in group_slots:
                sub = getattr(result, key)
                sub_params = group_slots[key].param
                for sub_key, sub_value in value.items():
                    if getattr(sub, sub_key) == sub_params[sub_key].default:
                        setattr(sub, sub_key, sub_value)
            elif getattr(result, key) == params[key].default:
                setattr(result, key, value)
        return result
