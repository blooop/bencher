from __future__ import annotations

import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


class HeatmapResult(HoloviewResult):
    """Heatmap visualizations using Plotly."""

    def to_plot(  # pylint: disable=unused-argument
        self,
        result_var=None,
        tap_var=None,
        tap_container=None,
        tap_container_direction=None,
        target_dimension=2,
        override=True,
        use_tap=None,
        **kwargs,
    ):
        return self.to_heatmap(
            result_var=result_var,
            target_dimension=target_dimension,
            override=override,
            **kwargs,
        )

    def to_heatmap(  # pylint: disable=unused-argument
        self,
        result_var=None,
        tap_var=None,
        tap_container=None,
        tap_container_direction=None,
        target_dimension=2,
        override=True,
        use_tap=None,
        **kwargs,
    ):
        return self.filter(
            self.to_heatmap_ds,
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(2, None),
            panel_range=VarRange(0, None),
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar,),
            override=override,
            **kwargs,
        )

    def to_heatmap_ds(self, dataset: xr.Dataset, result_var: Parameter, **_kwargs):
        if len(dataset.dims) >= 2:
            x_name = self.bench_cfg.input_vars[0].name
            y_name = self.bench_cfg.input_vars[1].name
            C = result_var.name
            title = f"Heatmap of {C}"

            if self._use_holomap_for_time(dataset):

                def make_heatmap(ds_t):
                    return self._make_heatmap_fig(ds_t, x_name, y_name, C, title, result_var)

                return self._build_time_holomap(dataset, C, make_heatmap)

            return self._make_heatmap_fig(dataset, x_name, y_name, C, title, result_var)
        return None

    def _make_heatmap_fig(self, dataset, x_name, y_name, C, title, result_var):
        da = dataset[C]
        x_vals = da.coords[x_name].values
        y_vals = da.coords[y_name].values
        z_vals = da.values

        # Ensure z is 2D (x by y)
        if z_vals.ndim == 1:
            return None
        # z_vals shape may be (y, x) or (x, y) depending on dim order
        dim_names = list(da.dims)
        if dim_names[0] == y_name:
            z_2d = z_vals
        else:
            z_2d = z_vals.T

        fig = go.Figure(
            data=go.Heatmap(
                x=[str(v) for v in x_vals],
                y=[str(v) for v in y_vals],
                z=z_2d,
                colorscale="Plasma",
                colorbar=dict(title=f"{C} [{getattr(result_var, 'units', '')}]"),
            )
        )
        fig.update_layout(
            **self._default_layout(title=title),
            xaxis_title=x_name,
            yaxis_title=y_name,
        )
        return fig

    # Keep legacy method signatures for backward compat
    def to_heatmap_container_tap_ds(self, dataset, result_var, **kwargs):
        return self.to_heatmap_ds(dataset, result_var, **kwargs)

    def to_heatmap_single(  # pylint: disable=unused-argument
        self, result_var, override=True, reduce=ReduceType.AUTO, **kwargs
    ):
        return None

    def to_heatmap_tap(  # pylint: disable=unused-argument
        self, result_var, reduce=ReduceType.AUTO, **kwargs
    ):
        return None
