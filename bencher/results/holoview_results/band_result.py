from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import SCALAR_RESULT_TYPES
from bencher.results.holoview_results.holoview_result import HoloviewResult


class BandResult(HoloviewResult):
    """Percentile band plot using Plotly.

    Shows nested shaded bands (10th-90th and 25th-75th percentiles)
    with a median line and individual scatter points.
    """

    def to_plot(self, result_var=None, override=True, **kwargs):
        return self.to_band(result_var=result_var, override=override, **kwargs)

    def to_band(self, result_var=None, override=True, **kwargs):
        band_agg_dims = kwargs.pop("agg_over_dims", None)
        kwargs.pop("agg_fn", None)
        return self.filter(
            self.to_band_ds,
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, None),
            input_range=VarRange(0, None),
            reduce=ReduceType.NONE,
            target_dimension=None,
            result_var=result_var,
            result_types=SCALAR_RESULT_TYPES,
            override=override,
            agg_over_dims=None,
            band_agg_dims=band_agg_dims,
            **kwargs,
        )

    def to_band_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        var = result_var.name
        agg_over_dims = kwargs.pop("band_agg_dims", None)
        explicit_title = kwargs.pop("title", None)
        units = getattr(result_var, "units", "") or ""

        use_holomap = self._use_holomap_for_time(dataset)
        if use_holomap:
            return self._band_over_time(
                dataset, var, explicit_title, agg_over_dims, units=units, **kwargs
            )

        # Without over_time: find a continuous x-axis from remaining dims
        return self._band_static(dataset, var, explicit_title, agg_over_dims, units=units, **kwargs)

    def _band_over_time(self, dataset, var, title, agg_over_dims=None, units="", **kwargs):
        da = dataset[var]
        sample_dims = [d for d in da.dims if d != "over_time"]
        if agg_over_dims:
            sample_dims = [d for d in sample_dims if d in agg_over_dims or d == "repeat"]
        if title is None:
            agg_names = [d for d in sample_dims if d != "repeat"]
            agg_str = ", ".join(agg_names) if agg_names else "repeat"
            title = f"{var} vs over_time (aggregated over {agg_str})"
        if not sample_dims:
            return None

        # Reshape to (n_time, n_samples) using numpy directly.
        # Avoids xarray .stack() which fails on Arrow-backed string coords.
        time_axis = list(da.dims).index("over_time")
        raw = np.asarray(da.values, dtype=float)
        values = np.moveaxis(raw, time_axis, 0).reshape(da.sizes["over_time"], -1)
        time_coords = da.coords["over_time"].values

        return self._build_band_fig(time_coords, values, var, title, "over_time", units, **kwargs)

    def _band_static(self, dataset, var, title, agg_over_dims, units="", **kwargs):
        da = dataset[var]
        all_dims = list(da.dims)
        agg_set = set(agg_over_dims) if agg_over_dims else set()
        candidate_x = [d for d in all_dims if d not in agg_set and d != "repeat"]
        if not candidate_x:
            return None
        x_dim = candidate_x[0]
        sample_dims = [d for d in all_dims if d != x_dim]
        if title is None:
            agg_names = [d for d in sample_dims if d != "repeat"]
            agg_str = ", ".join(agg_names) if agg_names else "repeat"
            title = f"{var} vs {x_dim} (aggregated over {agg_str})"
        if not sample_dims:
            return None

        stacked = da.stack(sample=sample_dims).transpose(x_dim, "sample")
        values = stacked.values
        x_coords = da.coords[x_dim].values

        return self._build_band_fig(x_coords, values, var, title, x_dim, units, **kwargs)

    @staticmethod
    def _build_band_fig(x_coords, values, var, title, x_dim, units="", **kwargs):
        max_scatter_points = kwargs.pop("max_scatter_points", 50_000)
        enable_scatter = kwargs.pop("enable_scatter", True)

        p10 = np.nanpercentile(values, 10, axis=1)
        p25 = np.nanpercentile(values, 25, axis=1)
        p50 = np.nanpercentile(values, 50, axis=1)
        p75 = np.nanpercentile(values, 75, axis=1)
        p90 = np.nanpercentile(values, 90, axis=1)

        x_str = [str(v) for v in x_coords]
        fig = go.Figure()

        # Outer band: 10th-90th
        fig.add_trace(
            go.Scatter(
                x=x_str + x_str[::-1],
                y=np.concatenate([p90, p10[::-1]]).tolist(),
                fill="toself",
                fillcolor="rgba(70,130,180,0.2)",
                line=dict(color="rgba(255,255,255,0)"),
                name="10th\u201390th pctl",
                hoverinfo="skip",
            )
        )

        # Inner band: 25th-75th
        fig.add_trace(
            go.Scatter(
                x=x_str + x_str[::-1],
                y=np.concatenate([p75, p25[::-1]]).tolist(),
                fill="toself",
                fillcolor="rgba(70,130,180,0.4)",
                line=dict(color="rgba(255,255,255,0)"),
                name="25th\u201375th pctl",
                hoverinfo="skip",
            )
        )

        # Median line
        fig.add_trace(
            go.Scatter(
                x=x_str,
                y=p50.tolist(),
                mode="lines",
                name="median",
                line=dict(color="steelblue", width=2),
            )
        )

        # Scatter points
        if enable_scatter:
            n_x, n_samples = values.shape
            total_points = n_x * n_samples
            if total_points > 0:
                full_x = np.repeat(x_coords, n_samples)
                full_y = values.ravel()
                if total_points > max_scatter_points:
                    idx = np.linspace(0, total_points - 1, max_scatter_points, dtype=int)
                    full_x = full_x[idx]
                    full_y = full_y[idx]
                mask = ~np.isnan(full_y)
                fig.add_trace(
                    go.Scatter(
                        x=[str(v) for v in full_x[mask]],
                        y=full_y[mask].tolist(),
                        mode="markers",
                        name="samples",
                        marker=dict(color="grey", size=3, opacity=0.3),
                    )
                )

        ylabel = f"{var} [{units}]" if units else var
        fig.update_layout(
            title=title,
            xaxis_title=x_dim,
            yaxis_title=ylabel,
            width=600,
            height=500,
            margin=dict(t=60, b=60, r=40, l=60),
            template="plotly_white",
            legend=dict(x=1.02, y=1, xanchor="left"),
        )
        return fig
