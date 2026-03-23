"""Plotly-based result rendering for bencher.

Replaces HoloViews/Panel embed pipeline with native Plotly figures.
Plotly handles interactivity client-side (sliders, hover, zoom) so
report.save() simply serializes JSON — no server-side pre-rendering.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import xarray as xr
from param import Parameter

from bencher.results.video_result import VideoResult
from bencher.results.bench_result_base import ReduceType

# Default plot dimensions
DEFAULT_WIDTH = 600
DEFAULT_HEIGHT = 500


class PlotlyResult(VideoResult):
    """Base class providing Plotly-based plotting utilities.

    Replaces HoloviewResult for all chart types.  Over_time is handled
    via Plotly dropdown menus (visibility toggling) which renders purely
    client-side.
    """

    @staticmethod
    def _default_layout(title: str = "", width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, **extra):
        """Return a base layout dict for Plotly figures."""
        layout = dict(
            title=title,
            width=width,
            height=height,
            margin=dict(t=60, b=60, r=40, l=60),
            hovermode="closest",
            template="plotly_white",
        )
        layout.update(extra)
        return layout

    def _use_slider_for_time(self, dataset: xr.Dataset) -> bool:
        """Check whether over_time should be rendered via a Plotly slider."""
        return (
            self.bench_cfg.over_time
            and "over_time" in dataset.dims
            and dataset.sizes["over_time"] > 1
        )

    @staticmethod
    def subsample_indices(n, max_points):
        """Return evenly-spaced indices into a length-*n* array.

        Always includes the first and last index.
        """
        if max_points is None or n <= max_points:
            return range(n)
        return np.unique(np.linspace(0, n - 1, max_points, dtype=int)).tolist()

    @staticmethod
    def _mean_over_time(dataset, result_var_name):
        """Average a dataset across all time points.

        Produces a ``_std`` variable via the law of total variance when
        a per-time-point ``_std`` already exists.
        """
        std_var = f"{result_var_name}_std"
        new_ds = dataset.mean(dim="over_time")
        var_of_means = dataset[result_var_name].var(dim="over_time")
        if std_var in dataset.data_vars:
            mean_of_vars = (dataset[std_var] ** 2).mean(dim="over_time")
            new_ds[std_var] = (mean_of_vars + var_of_means) ** 0.5
        else:
            new_ds[std_var] = var_of_means**0.5
        return new_ds

    def _build_time_dropdown_fig(self, dataset, result_var_name, make_traces_fn, layout_base=None):
        """Build a Plotly figure with a dropdown to select time points.

        ``make_traces_fn(ds_t)`` should return a list of ``go.BaseTraceType``
        for one time slice.  The dropdown toggles trace visibility so the
        browser never re-renders — it just shows/hides pre-computed traces.

        Optionally adds an aggregated view as the last dropdown entry.
        """
        times = dataset.coords["over_time"].values
        n_time = len(times)
        slider_indices = self.subsample_indices(n_time, self.bench_cfg.max_slider_points)

        # Collect traces per time point
        all_traces = []
        group_sizes = []
        time_labels = []

        for idx in slider_indices:
            t = times[idx]
            ds_t = dataset.sel(over_time=t)
            traces = make_traces_fn(ds_t)
            all_traces.extend(traces)
            group_sizes.append(len(traces))
            time_labels.append(str(t))

        # Optionally add aggregated view
        if n_time > 1 and self.bench_cfg.show_aggregated_time_tab:
            ds_agg = self._mean_over_time(dataset, result_var_name)
            agg_traces = make_traces_fn(ds_agg)
            all_traces.extend(agg_traces)
            group_sizes.append(len(agg_traces))
            time_labels.append("All (aggregated)")

        # Build visibility masks for the dropdown
        total_traces = len(all_traces)
        buttons = []
        offset = 0
        for i, label in enumerate(time_labels):
            vis = [False] * total_traces
            for j in range(group_sizes[i]):
                vis[offset + j] = True
            buttons.append(dict(
                label=label,
                method="update",
                args=[{"visible": vis}],
            ))
            offset += group_sizes[i]

        # Default: show last time point (most recent)
        last_non_agg = len(time_labels) - 1
        if self.bench_cfg.show_aggregated_time_tab and n_time > 1:
            last_non_agg = len(time_labels) - 2
        default_vis = [False] * total_traces
        offset = sum(group_sizes[:last_non_agg])
        for j in range(group_sizes[last_non_agg]):
            default_vis[offset + j] = True
        for trace, vis in zip(all_traces, default_vis):
            trace.visible = vis

        fig = go.Figure(data=all_traces)

        layout = layout_base or {}
        layout["updatemenus"] = [
            dict(
                active=last_non_agg,
                buttons=buttons,
                x=0.0,
                xanchor="left",
                y=-0.15,
                yanchor="top",
                direction="up",
                type="dropdown",
                showactive=True,
            )
        ]
        # Extra bottom margin for dropdown
        if "margin" not in layout:
            layout["margin"] = dict(t=60, b=120, r=40, l=60)
        else:
            layout["margin"] = dict(layout["margin"], b=max(layout.get("margin", {}).get("b", 60), 120))

        fig.update_layout(**layout)
        return fig

    def _wrap_plotly(self, fig: go.Figure, name: str = "plotly") -> go.Figure:
        """Return the Plotly figure directly (no Panel wrapper).

        Kept as a method so subclasses can override if needed.
        """
        return fig

    def title_from_ds(self, dataset, result_var, **kwargs):
        """Build a plot title from dataset dims and result var."""
        if "title" in kwargs:
            return kwargs["title"]
        if isinstance(dataset, xr.DataArray):
            parts = [dataset.name] + list(dataset.dims)
        else:
            parts = [result_var.name] + list(dataset.sizes)
        return " vs ".join(parts)
