"""Plot plugin infrastructure for bencher.

The public surface a plugin author depends on:
    - BenchData: frozen value handed to render(), defines what plugins receive.
    - PlotPlugin: protocol all plugins satisfy.
    - plot_plugin: decorator for the function form.
    - register_plugin / unregister_plugin / get_registry: explicit registration API.
    - PlotFilter / VarRange (re-exported): for declaring match rules.

Bencher's internal call sites do not yet depend on this package. Migration of the
built-in chart types onto the plugin mechanism happens in subsequent PRs."""

from __future__ import annotations

from bencher.plotting.plot_filter import PlotFilter, VarRange

from bencher.plugins.bench_data import BenchData, CacheHandle, RunMeta
from bencher.plugins.plugin import PlotPlugin, plot_plugin
from bencher.plugins.registry import (
    ENTRY_POINT_GROUP,
    PluginRegistry,
    get_registry,
    register_plugin,
    unregister_plugin,
)

__all__ = [
    "BenchData",
    "CacheHandle",
    "ENTRY_POINT_GROUP",
    "PlotFilter",
    "PlotPlugin",
    "PluginRegistry",
    "RunMeta",
    "VarRange",
    "get_registry",
    "plot_plugin",
    "register_plugin",
    "unregister_plugin",
]
