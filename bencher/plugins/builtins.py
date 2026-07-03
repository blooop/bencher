"""Built-in chart types wrapped as plot plugins (A1 Phase 2).

Each wrapper delegates to the existing renderer method on the live BenchResult
(carried in ``BenchData.legacy_result``), so renderer logic is unchanged — this
phase only moves *dispatch* onto the plugin registry. The registry-level match
rule is permissive (``PlotFilter.match_all()``) because today's renderers build
their shape filters dynamically inside ``to_plot`` (scenario lists, over_time
special cases) and return ``None`` on mismatch; centralizing those filters into
declarative signatures is the plot-selection redesign (A2), not this phase.

Priorities encode the legacy ``default_plot_callbacks()`` ordering so reports
render plots in exactly the same order as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import panel as pn

from bencher.plotting.plot_filter import PlotFilter
from bencher.plugins.bench_data import BenchData
from bencher.plugins.registry import register_plugin


@dataclass(frozen=True)
class LegacyResultPlugin:
    """Thin plugin adapter over a legacy ``BenchResult`` renderer method."""

    name: str
    backend: str
    match: PlotFilter
    priority: int
    requires: frozenset[str]
    callback: Callable

    def render(self, data: BenchData) -> Optional[pn.viewable.Viewable]:
        return self.callback(data.legacy_result, **data.render_kwargs)


def _builtin_specs() -> list[tuple[str, str, Callable]]:
    """(name, backend, callback) for the default chart set, in legacy order."""
    # Imported here (not module level) to avoid a circular import: the result
    # classes' module tree imports the plugin registry for to_auto dispatch.
    from bencher.results.holoview_results.bar_result import BarResult
    from bencher.results.holoview_results.distribution_result.box_whisker_result import (
        BoxWhiskerResult,
    )
    from bencher.results.holoview_results.curve_result import CurveResult
    from bencher.results.holoview_results.line_result import LineResult
    from bencher.results.holoview_results.heatmap_result import HeatmapResult
    from bencher.results.histogram_result import HistogramResult
    from bencher.results.volume_result import VolumeResult
    from bencher.results.pane_result import PaneResult

    return [
        ("bar", "holoviews", BarResult.to_plot),
        ("box_whisker", "holoviews", BoxWhiskerResult.to_plot),
        ("curve", "holoviews", CurveResult.to_plot),
        ("line", "holoviews", LineResult.to_plot),
        ("heatmap", "holoviews", HeatmapResult.to_plot),
        ("histogram", "holoviews", HistogramResult.to_plot),
        ("volume", "plotly", VolumeResult.to_plot),
        ("panes", "panel", PaneResult.to_panes),
    ]


# Name of the plugin that renders pane-type results (images, videos, rerun, ...);
# excluded by to_auto(numeric_only=True).
PANES_PLUGIN_NAME = "panes"

# callback function -> plugin name, so to_auto can translate legacy
# plot_list/remove_plots entries (callables) into registry names.
CALLBACK_TO_PLUGIN: dict[Callable, str] = {}


def register_builtin_plugins() -> None:
    """Register the default chart set with the global registry. Idempotent."""
    priority = 100
    for name, backend, callback in _builtin_specs():
        register_plugin(
            LegacyResultPlugin(
                name=name,
                backend=backend,
                match=PlotFilter.match_all(),
                priority=priority,
                requires=frozenset({"legacy_result"}),
                callback=callback,
            )
        )
        CALLBACK_TO_PLUGIN[callback] = name
        priority -= 5
