"""Plotly-based result rendering base class for bencher.

Replaces the former HoloViews/Panel embed pipeline with native Plotly
figures. Plotly handles interactivity client-side (sliders, hover, zoom)
so report.save() simply serializes JSON — no server-side pre-rendering
of HoloMap widget states.
"""

from __future__ import annotations

import numpy as np
import panel as pn
import plotly.graph_objects as go
from param import Parameter
from itertools import product as iterproduct
import xarray as xr

from bencher.utils import listify
from bencher.results.video_result import VideoResult
from bencher.results.bench_result_base import ReduceType
from bencher.variables.results import ResultImage, ResultVideo

# Default plot dimensions
DEFAULT_WIDTH = 600
DEFAULT_HEIGHT = 500

# Plotly color sequence (matches plotly_white template)
PLOTLY_COLORS = [
    "#636EFA",
    "#EF553B",
    "#00CC96",
    "#AB63FA",
    "#FFA15A",
    "#19D3F3",
    "#FF6692",
    "#B6E880",
    "#FF97FF",
    "#FECB52",
]

_AGG_TITLE = "All Time Points (aggregated)"

# Flag to enable or disable tap tool functionality in visualizations
use_tap = True


class HoloviewResult(VideoResult):
    """Base class providing Plotly-based plotting utilities.

    Despite the legacy name (kept for backward compatibility with the
    class hierarchy), all plots are now rendered via Plotly.
    """

    @staticmethod
    def set_default_opts(width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> dict:
        """Set default options for visualizations.

        Args:
            width: Default width for visualizations. Defaults to 600.
            height: Default height for visualizations. Defaults to 600.

        Returns:
            dict: Dictionary containing width and height settings.
        """
        return {"width": width, "height": height}

    @staticmethod
    def _default_layout(title="", width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, **extra):
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

    def _use_holomap_for_time(self, dataset: xr.Dataset) -> bool:
        """Check whether over_time should be rendered via a Plotly dropdown."""
        return (
            self.bench_cfg.over_time
            and "over_time" in dataset.dims
            and dataset.sizes["over_time"] > 1
        )

    # Alias for backward compat
    _use_slider_for_time = _use_holomap_for_time

    @staticmethod
    def _apply_opts(plot, **opts_kwargs):
        """No-op for backward compat — Plotly figures don't use .opts()."""
        return plot

    @staticmethod
    def _over_time_kdims() -> list:
        """Return the kdim list for over_time — kept for compat."""
        return ["over_time"]

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
        """
        times = dataset.coords["over_time"].values
        n_time = len(times)
        slider_indices = self.subsample_indices(n_time, self.bench_cfg.max_slider_points)

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

        total_traces = len(all_traces)
        buttons = []
        offset = 0
        for i, label in enumerate(time_labels):
            vis = [False] * total_traces
            for j in range(group_sizes[i]):
                vis[offset + j] = True
            buttons.append(
                dict(
                    label=label,
                    method="update",
                    args=[{"visible": vis}],
                )
            )
            offset += group_sizes[i]

        # Default: show last non-aggregated time point
        last_non_agg = len(time_labels) - 1
        if self.bench_cfg.show_aggregated_time_tab and n_time > 1:
            last_non_agg = len(time_labels) - 2
        default_vis = [False] * total_traces
        off = sum(group_sizes[:last_non_agg])
        for j in range(group_sizes[last_non_agg]):
            default_vis[off + j] = True
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
        if "margin" not in layout:
            layout["margin"] = dict(t=60, b=120, r=40, l=60)
        else:
            layout["margin"]["b"] = max(layout.get("margin", {}).get("b", 60), 120)

        fig.update_layout(**layout)
        return fig

    def _build_time_holomap(self, dataset, result_var_name, make_plot_fn):
        """Build a Plotly figure with time dropdown from a dataset callback.

        ``make_plot_fn`` receives a dataset *without* over_time and returns
        a ``go.Figure``.  We extract traces from each figure and compose
        them into a single figure with a dropdown menu.
        """

        def make_traces_fn(ds_t):
            fig = make_plot_fn(ds_t)
            if isinstance(fig, go.Figure):
                return list(fig.data)
            # Fallback: if it's a Panel pane wrapping a Plotly figure
            if hasattr(fig, "object") and isinstance(fig.object, (go.Figure, dict)):
                f = fig.object
                if isinstance(f, dict):
                    return list(go.Figure(f).data)
                return list(f.data)
            # Can't extract traces — wrap in a single dummy
            return [go.Scatter(x=[], y=[], name="(unsupported)")]

        # Get layout from first time point's figure
        times = dataset.coords["over_time"].values
        idx0 = self.subsample_indices(len(times), self.bench_cfg.max_slider_points)[0]
        ds_t0 = dataset.sel(over_time=times[idx0])
        fig0 = make_plot_fn(ds_t0)
        layout_base = {}
        if isinstance(fig0, go.Figure):
            layout_base = fig0.layout.to_plotly_json()
            # Remove data-specific items
            layout_base.pop("template", None)

        return self._build_time_dropdown_fig(dataset, result_var_name, make_traces_fn, layout_base)

    def _build_time_holomap_raw(self, da, make_plot_fn):
        """Build time dropdown for distribution plots.

        ``make_plot_fn`` receives a DataArray that retains the ``over_time``
        dimension (a single-element slice for per-time-point entries, or the
        full array for the aggregated tab).
        """
        times = da.coords["over_time"].values
        n_time = len(times)
        slider_indices = self.subsample_indices(n_time, self.bench_cfg.max_slider_points)

        all_traces = []
        group_sizes = []
        time_labels = []

        for idx in slider_indices:
            t = times[idx]
            da_t = da.isel(over_time=slice(idx, idx + 1))
            fig = make_plot_fn(da_t)
            if isinstance(fig, go.Figure):
                traces = list(fig.data)
            else:
                traces = [go.Scatter(x=[], y=[])]
            all_traces.extend(traces)
            group_sizes.append(len(traces))
            time_labels.append(str(t))

        if n_time > 1 and self.bench_cfg.show_aggregated_time_tab:
            fig = make_plot_fn(da)
            if isinstance(fig, go.Figure):
                traces = list(fig.data)
            else:
                traces = [go.Scatter(x=[], y=[])]
            all_traces.extend(traces)
            group_sizes.append(len(traces))
            time_labels.append("All (aggregated)")

        total_traces = len(all_traces)
        buttons = []
        offset = 0
        for i, label in enumerate(time_labels):
            vis = [False] * total_traces
            for j in range(group_sizes[i]):
                vis[offset + j] = True
            buttons.append(dict(label=label, method="update", args=[{"visible": vis}]))
            offset += group_sizes[i]

        last_non_agg = len(time_labels) - 1
        if self.bench_cfg.show_aggregated_time_tab and n_time > 1:
            last_non_agg = len(time_labels) - 2
        default_vis = [False] * total_traces
        off = sum(group_sizes[:last_non_agg])
        for j in range(group_sizes[last_non_agg]):
            default_vis[off + j] = True
        for trace, vis in zip(all_traces, default_vis):
            trace.visible = vis

        fig = go.Figure(data=all_traces)
        fig.update_layout(
            updatemenus=[
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
            ],
            margin=dict(t=60, b=120, r=40, l=60),
            template="plotly_white",
        )
        return fig

    def _build_curve_overlay(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> go.Figure:
        """Build a line (+ optional error band) figure for a single time slice.

        When ``_std`` exists, renders a filled error band.
        Groups by categorical dimensions if present.
        """
        var = result_var.name
        std_var = f"{var}_std"
        has_spread = std_var in dataset.data_vars
        title = self.title_from_ds(dataset, result_var, **kwargs)

        float_names = [fv.name for fv in self.plt_cnt_cfg.float_vars]
        ds_dims = list(dataset.dims)
        kdims = [d for d in ds_dims if d in float_names] or ds_dims[:1]
        groupby = [d for d in ds_dims if d not in kdims]

        fig = go.Figure()
        x_dim = kdims[0] if kdims else ds_dims[0] if ds_dims else var

        if not groupby:
            x_vals = (
                dataset.coords[x_dim].values
                if x_dim in dataset.coords
                else np.arange(len(dataset[var].values))
            )
            y_vals = dataset[var].values.ravel()
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines",
                    name=var,
                )
            )
            if has_spread:
                std_vals = dataset[std_var].values.ravel()
                upper = y_vals + std_vals
                lower = y_vals - std_vals
                fig.add_trace(
                    go.Scatter(
                        x=np.concatenate([x_vals, x_vals[::-1]]),
                        y=np.concatenate([upper, lower[::-1]]),
                        fill="toself",
                        fillcolor="rgba(99,110,250,0.2)",
                        line=dict(color="rgba(255,255,255,0)"),
                        name=f"{var} ± std",
                        showlegend=True,
                        hoverinfo="skip",
                    )
                )
        else:
            group_coords = [dataset.coords[g].values for g in groupby]
            for ci, combo in enumerate(iterproduct(*group_coords)):
                sel = dict(zip(groupby, combo))
                group_ds = dataset.sel(**sel)
                label = ", ".join(str(v) for v in combo) if len(combo) > 1 else str(combo[0])
                color = PLOTLY_COLORS[ci % len(PLOTLY_COLORS)]

                x_vals = (
                    group_ds.coords[x_dim].values
                    if x_dim in group_ds.coords
                    else np.arange(len(group_ds[var].values))
                )
                y_vals = group_ds[var].values.ravel()
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=y_vals,
                        mode="lines",
                        name=label,
                        line=dict(color=color),
                    )
                )
                if has_spread:
                    std_vals = group_ds[std_var].values.ravel()
                    upper = y_vals + std_vals
                    lower = y_vals - std_vals
                    r, g_c, b = _hex_to_rgb(color)
                    fig.add_trace(
                        go.Scatter(
                            x=np.concatenate([x_vals, x_vals[::-1]]),
                            y=np.concatenate([upper, lower[::-1]]),
                            fill="toself",
                            fillcolor=f"rgba({r},{g_c},{b},0.2)",
                            line=dict(color="rgba(255,255,255,0)"),
                            name=f"{label} ± std",
                            showlegend=False,
                            hoverinfo="skip",
                        )
                    )

        fig.update_layout(
            **self._default_layout(title=title),
            xaxis_title=x_dim,
            yaxis_title=f"{var} [{getattr(result_var, 'units', '')}]",
            legend=dict(x=1.02, y=1, xanchor="left"),
        )
        return fig

    @staticmethod
    def _holomap_with_slider_bottom(hvobj, widgets=None):
        """Backward compat stub — returns input unchanged."""
        return hvobj

    def overlay_plots(self, plot_callback: callable):
        """Create combined figure by applying callback to each result variable."""
        figures = []
        for rv in self.bench_cfg.result_vars:
            res = plot_callback(rv)
            if res is not None and isinstance(res, go.Figure):
                figures.append(res)
        if not figures:
            return None
        if len(figures) == 1:
            return figures[0]
        # Merge traces into first figure
        combined = go.Figure(data=figures[0].data, layout=figures[0].layout)
        for f in figures[1:]:
            for trace in f.data:
                combined.add_trace(trace)
        return combined

    def layout_plots(self, plot_callback: callable):
        """Create layout of plots by applying callback to each result variable."""
        return self.overlay_plots(plot_callback)

    def time_widget(self, title: str) -> dict:
        """Backward compat — return widget config dict."""
        return {"title": title}

    def to_hv_type(self, hv_type, reduce=ReduceType.AUTO, **kwargs):
        """Backward compat stub."""
        return None

    def to_hv_container(self, container, reduce_type=ReduceType.AUTO, **kwargs):
        """Backward compat stub."""
        return None

    def result_var_to_container(self, result_var: Parameter) -> type:
        """Determine the appropriate container type for a given result variable."""
        if isinstance(result_var, ResultImage):
            return pn.pane.PNG
        return pn.pane.Video if isinstance(result_var, ResultVideo) else pn.Column

    def setup_results_and_containers(
        self,
        result_var_plots,
        container=None,
        **kwargs,
    ):
        """Set up containers for result variables."""
        result_var_plots = listify(result_var_plots)
        if container is None:
            containers = [self.result_var_to_container(rv) for rv in result_var_plots]
        else:
            containers = listify(container)
        cont_instances = [c(**kwargs) if c is not None else None for c in containers]
        return result_var_plots, cont_instances

    def to_error_bar(self, result_var=None, **kwargs):
        """Backward compat stub."""
        return None

    def to_points(self, reduce=ReduceType.AUTO):
        """Backward compat stub."""
        return None

    def to_nd_layout(self, hmap_name):
        """Backward compat stub."""
        return None

    def to_holomap(self, name=None):
        """Backward compat stub."""
        return None

    def to_holomap_list(self, hmap_names=None):
        """Backward compat stub."""
        return pn.Column()

    def get_nearest_holomap(self, name=None, **kwargs):
        """Backward compat stub."""
        return None

    def to_dynamic_map(self, name=None):
        """Backward compat stub."""
        return None

    def to_grid(self, inputs=None):
        """Backward compat stub."""
        return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


HoloviewResult.set_default_opts()
