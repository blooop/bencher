from __future__ import annotations

import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult, PLOTLY_COLORS


class LineResult(HoloviewResult):
    """Line plots using Plotly."""

    def to_plot(  # pylint: disable=unused-argument
        self,
        result_var=None,
        tap_var=None,
        tap_container=None,
        target_dimension=2,
        override=True,
        use_tap=None,
        **kwargs,
    ):
        return self.to_line(
            result_var=result_var,
            target_dimension=target_dimension,
            override=override,
            **kwargs,
        )

    def to_line(  # pylint: disable=unused-argument
        self,
        result_var=None,
        tap_var=None,
        tap_container=None,
        target_dimension=2,
        override=True,
        use_tap=None,
        **kwargs,
    ):
        if self.bench_cfg.over_time:
            float_range = VarRange(0, 1)
            input_range = VarRange(0, None)
        else:
            float_range = VarRange(1, 1)
            input_range = None
        return self.filter(
            self.to_line_ds,
            float_range=float_range,
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            panel_range=VarRange(0, None),
            input_range=input_range,
            reduce=ReduceType.SQUEEZE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar, ResultBool),
            override=override,
            **kwargs,
        )

    def to_line_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        da_plot = dataset[result_var.name]
        var = result_var.name

        # 0D + over_time: time-series line
        if not self.plt_cnt_cfg.float_vars and "over_time" in da_plot.dims:
            title = self.title_from_ds(da_plot, result_var, **kwargs)
            x_vals = da_plot.coords["over_time"].values
            y_vals = da_plot.values.ravel()
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=[str(v) for v in x_vals],
                    y=y_vals,
                    mode="lines+markers",
                    name=var,
                )
            )
            fig.update_layout(
                **self._default_layout(title=title),
                xaxis_title="over_time",
                yaxis_title=f"{var} [{getattr(result_var, 'units', '')}]",
            )
            return fig

        x_dim = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        title = self.title_from_ds(da_plot, result_var, **kwargs)

        if self._use_holomap_for_time(dataset):

            def make_line(ds_t):
                std_var = f"{var}_std"
                if std_var in ds_t.data_vars:
                    return self._build_curve_overlay(ds_t, result_var, **kwargs)
                return self._make_line_fig(ds_t, result_var, x_dim, by, title, **kwargs)

            return self._build_time_holomap(dataset, var, make_line)

        return self._make_line_fig(dataset, result_var, x_dim, by, title, **kwargs)

    def _make_line_fig(self, dataset, result_var, x_dim, by, title, **_kwargs):
        var = result_var.name
        fig = go.Figure()

        if by and by in dataset.dims:
            for ci, val in enumerate(dataset.coords[by].values):
                ds_sel = dataset.sel({by: val})
                x_vals = ds_sel.coords[x_dim].values
                y_vals = ds_sel[var].values.ravel()
                fig.add_trace(
                    go.Scatter(
                        x=x_vals,
                        y=y_vals,
                        mode="lines+markers",
                        name=str(val),
                        line=dict(color=PLOTLY_COLORS[ci % len(PLOTLY_COLORS)]),
                    )
                )
        else:
            x_vals = dataset.coords[x_dim].values if x_dim in dataset.coords else []
            y_vals = dataset[var].values.ravel()
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_vals,
                    mode="lines+markers",
                    name=var,
                )
            )

        fig.update_layout(
            **self._default_layout(title=title),
            xaxis_title=x_dim,
            yaxis_title=f"{var} [{getattr(result_var, 'units', '')}]",
        )
        return fig

    # Tap-based interactive plots are not supported in static Plotly
    # but we keep the method signature for backward compat
    def to_line_tap_ds(
        self, dataset, result_var, _result_var_plots=None, _container=None, **kwargs
    ):
        return self.to_line_ds(dataset, result_var, **kwargs)
