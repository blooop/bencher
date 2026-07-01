from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol, runtime_checkable

import panel as pn

from bencher.plotting.plot_filter import PlotFilter
from bencher.plugins.bench_data import BenchData


@runtime_checkable
class PlotPlugin(Protocol):
    """Stable public contract for plot plugins.

    A plugin renders a BenchData handle into a Panel-embeddable view. The plugin owns
    internal composition (linked hv.Layout, plotly.subplots, full Rerun blueprints, ...);
    bencher only does outer Panel-level composition over plugin outputs."""

    name: str
    backend: str
    match: PlotFilter
    priority: int
    requires: frozenset[str]

    def render(self, data: BenchData) -> pn.viewable.Viewable: ...


@dataclass
class _FunctionPlugin:
    """Concrete plugin synthesised by the @plot_plugin decorator. Class form is canonical
    for distributed plugins; this exists so a one-shot in-script plugin can be a single
    decorated function."""

    name: str
    backend: str
    match: PlotFilter
    priority: int
    requires: frozenset[str]
    _fn: Callable[[BenchData], pn.viewable.Viewable] = field(repr=False)

    def render(self, data: BenchData) -> pn.viewable.Viewable:
        return self._fn(data)


def plot_plugin(
    *,
    name: str,
    backend: str = "user",
    match: Optional[PlotFilter] = None,
    priority: int = 0,
    requires: Optional[frozenset[str] | set[str] | tuple[str, ...]] = None,
    register: bool = True,
) -> Callable[[Callable[[BenchData], pn.viewable.Viewable]], _FunctionPlugin]:
    """Wrap a function as a plot plugin and (by default) register it with the global
    registry. Returns the plugin object so callers can also register manually with
    register=False."""

    def decorator(fn: Callable[[BenchData], pn.viewable.Viewable]) -> _FunctionPlugin:
        # No match rule means "always eligible": PlotFilter() would match nothing
        # (its default VarRanges are empty), silently hiding the plugin forever.
        plugin = _FunctionPlugin(
            name=name,
            backend=backend,
            match=match if match is not None else PlotFilter.match_all(),
            priority=priority,
            requires=frozenset(requires) if requires else frozenset(),
            _fn=fn,
        )
        if register:
            from bencher.plugins.registry import register_plugin

            register_plugin(plugin)
        return plugin

    return decorator
