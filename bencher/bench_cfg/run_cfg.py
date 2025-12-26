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

# Mapping of delegated attribute names to their sub-config
_DELEGATION_MAP = {
    # Server
    "port": "server",
    "allow_ws_origin": "server",
    "show": "server",
    # Cache
    "cache_results": "cache",
    "clear_cache": "cache",
    "cache_samples": "cache",
    "only_hash_tag": "cache",
    "clear_sample_cache": "cache",
    "overwrite_sample_cache": "cache",
    "only_plot": "cache",
    # Execution
    "repeats": "execution",
    "level": "execution",
    "executor": "execution",
    "nightly": "execution",
    "headless": "execution",
    # Display
    "summarise_constant_inputs": "display",
    "print_bench_inputs": "display",
    "print_bench_results": "display",
    "print_pandas": "display",
    "print_xarray": "display",
    "serve_pandas": "display",
    "serve_pandas_flat": "display",
    "serve_xarray": "display",
    # Visualization
    "auto_plot": "visualization",
    "use_holoview": "visualization",
    "use_optuna": "visualization",
    "render_plotly": "visualization",
    "raise_duplicate_exception": "visualization",
    "plot_size": "visualization",
    "plot_width": "visualization",
    "plot_height": "visualization",
    # Time
    "over_time": "time",
    "clear_history": "time",
    "time_event": "time",
    "run_tag": "time",
    "run_date": "time",
}


class BenchRunCfg(param.Parameterized):
    """Benchmark run configuration composing cache, execution, display, visualization, and time.

    Access parameters directly (cfg.cache_results) or via sub-config (cfg.cache.cache_results).
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

        Handles both new-style (sub-config objects) and legacy-style (flat parameters)
        initialization for backward compatibility.
        """
        # Extract sub-config objects if provided
        server = params.pop("server", None) or BenchPlotSrvCfg()
        cache = params.pop("cache", None) or CacheCfg()
        execution = params.pop("execution", None) or ExecutionCfg()
        display = params.pop("display", None) or DisplayCfg()
        visualization = params.pop("visualization", None) or VisualizationCfg()
        time_cfg = params.pop("time", None) or TimeCfg()

        # Route legacy flat parameters to appropriate sub-config
        sub_configs = {
            "server": server,
            "cache": cache,
            "execution": execution,
            "display": display,
            "visualization": visualization,
            "time": time_cfg,
        }
        for key in list(params.keys()):
            if key in _DELEGATION_MAP:
                sub_name = _DELEGATION_MAP[key]
                setattr(sub_configs[sub_name], key, params.pop(key))

        # Initialize with sub-configs
        super().__init__(
            server=server,
            cache=cache,
            execution=execution,
            display=display,
            visualization=visualization,
            time=time_cfg,
            **params,
        )

    def __getattr__(self, name):
        """Delegate attribute access to sub-configs for backward compatibility."""
        if name in _DELEGATION_MAP:
            sub_name = _DELEGATION_MAP[name]
            sub_cfg = object.__getattribute__(self, sub_name)
            return getattr(sub_cfg, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        """Delegate attribute setting to sub-configs for backward compatibility."""
        if name in _DELEGATION_MAP:
            sub_name = _DELEGATION_MAP[name]
            sub_cfg = object.__getattribute__(self, sub_name)
            setattr(sub_cfg, name, value)
        else:
            super().__setattr__(name, value)

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
            cache_results=args.use_cache,
            only_plot=args.only_plot,
            port=args.port,
            nightly=args.nightly,
            time_event=args.time_event,
            repeats=args.repeats,
        )

    def deep(self):
        """Create a deep copy of this configuration."""
        return deepcopy(self)
