"""Configuration class for benchmark execution parameters."""

from __future__ import annotations

import argparse
from copy import deepcopy

import param

from bencher.bench_cfg.server_cfg import BenchPlotSrvCfg
from bencher.bench_cfg.cache_cfg import CacheCfg
from bencher.bench_cfg.execution_cfg import ExecutionCfg
from bencher.bench_cfg.display_cfg import DisplayCfg
from bencher.bench_cfg.visualization_cfg import VisualizationCfg
from bencher.bench_cfg.time_cfg import TimeCfg

# Sub-config classes mapped to their attribute names
_SUBCONFIG_CLASSES = {
    "server": BenchPlotSrvCfg,
    "cache": CacheCfg,
    "execution": ExecutionCfg,
    "display": DisplayCfg,
    "visualization": VisualizationCfg,
    "time": TimeCfg,
}


class BenchRunCfg(param.Parameterized):
    """Benchmark run configuration composing cache, execution, display, visualization, and time.

    Access parameters via sub-configs (e.g., cfg.cache.cache_results, cfg.execution.repeats).
    """

    # Composed sub-configurations
    server: BenchPlotSrvCfg = param.ClassSelector(
        class_=BenchPlotSrvCfg,
        default=None,
        instantiate=True,
        doc="Plot server configuration",
    )
    cache: CacheCfg = param.ClassSelector(
        class_=CacheCfg,
        default=None,
        instantiate=True,
        doc="Caching behavior configuration",
    )
    execution: ExecutionCfg = param.ClassSelector(
        class_=ExecutionCfg,
        default=None,
        instantiate=True,
        doc="Execution settings configuration",
    )
    display: DisplayCfg = param.ClassSelector(
        class_=DisplayCfg,
        default=None,
        instantiate=True,
        doc="Display and reporting configuration",
    )
    visualization: VisualizationCfg = param.ClassSelector(
        class_=VisualizationCfg,
        default=None,
        instantiate=True,
        doc="Visualization and plotting configuration",
    )
    time: TimeCfg = param.ClassSelector(
        class_=TimeCfg,
        default=None,
        instantiate=True,
        doc="Time and history configuration",
    )

    def __init__(self, **params):
        """Initialize BenchRunCfg with composed sub-configurations.

        Sub-configs are automatically instantiated if not provided.
        Nested parameters (e.g., run_tag, cache_results) are automatically routed to sub-configs.
        """
        # Extract sub-config objects if provided, otherwise create defaults
        server = params.pop("server", None) or BenchPlotSrvCfg()
        cache = params.pop("cache", None) or CacheCfg()
        execution = params.pop("execution", None) or ExecutionCfg()
        display = params.pop("display", None) or DisplayCfg()
        visualization = params.pop("visualization", None) or VisualizationCfg()
        time_cfg = params.pop("time", None) or TimeCfg()

        # Route nested parameters to appropriate sub-configs
        subconfig_instances = {
            "server": server,
            "cache": cache,
            "execution": execution,
            "display": display,
            "visualization": visualization,
            "time": time_cfg,
        }

        # Distribute remaining params to sub-configs based on their parameter definitions
        remaining_params = {}
        for param_name, param_value in list(params.items()):
            routed = False
            for subconfig_name, subconfig_cls in _SUBCONFIG_CLASSES.items():
                if hasattr(subconfig_cls.param, param_name):
                    # This parameter belongs to this sub-config
                    setattr(subconfig_instances[subconfig_name], param_name, param_value)
                    routed = True
                    break
            if not routed:
                # Keep unrouted params for the parent class
                remaining_params[param_name] = param_value

        # Initialize with sub-configs
        super().__init__(
            server=subconfig_instances["server"],
            cache=subconfig_instances["cache"],
            execution=subconfig_instances["execution"],
            display=subconfig_instances["display"],
            visualization=subconfig_instances["visualization"],
            time=subconfig_instances["time"],
            **remaining_params,
        )

    @staticmethod
    def from_cmd_line() -> BenchRunCfg:  # pragma: no cover
        """Create a BenchRunCfg by parsing command line arguments.

        Parses command line arguments to create a configuration for benchmark runs.

        Returns:
            BenchRunCfg: Configuration object with settings from command line arguments
        """
        parser = argparse.ArgumentParser(description="benchmark")

        parser.add_argument(
            "--use-cache",
            action="store_true",
            help=CacheCfg.param.cache_results.doc,
        )
        parser.add_argument(
            "--only-plot",
            action="store_true",
            help=CacheCfg.param.only_plot.doc,
        )
        parser.add_argument(
            "--port",
            type=int,
            help=BenchPlotSrvCfg.param.port.doc,
        )
        parser.add_argument(
            "--nightly",
            action="store_true",
            help="Turn on nightly benchmarking",
        )
        parser.add_argument(
            "--time_event",
            type=str,
            default=TimeCfg.param.time_event.default,
            help=TimeCfg.param.time_event.doc,
        )
        parser.add_argument(
            "--repeats",
            type=int,
            default=ExecutionCfg.param.repeats.default,
            help=ExecutionCfg.param.repeats.doc,
        )

        args = parser.parse_args()

        return BenchRunCfg(
            cache=CacheCfg(cache_results=args.use_cache, only_plot=args.only_plot),
            server=BenchPlotSrvCfg(port=args.port),
            execution=ExecutionCfg(nightly=args.nightly, repeats=args.repeats),
            time=TimeCfg(time_event=args.time_event),
        )

    def deep(self):
        """Create a deep copy of this configuration."""
        return deepcopy(self)
