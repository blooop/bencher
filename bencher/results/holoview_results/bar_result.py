from __future__ import annotations

import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult, PLOTLY_COLORS


class BarResult(HoloviewResult):
    """Bar charts using Plotly."""

    def to_plot(self, result_var=None, override=True, **kwargs):
        return self.to_bar(result_var, override, **kwargs)

    def to_bar(self, result_var=None, override=True, target_dimension=2, **kwargs):
        input_range = VarRange(0, None) if self.bench_cfg.over_time else None
        common = {
            "float_range": VarRange(0, 0),
            "cat_range": VarRange(0, None),
            "panel_range": VarRange(0, None),
            "input_range": input_range,
            "target_dimension": target_dimension,
            "result_var": result_var,
            "override": override,
            **kwargs,
        }

        scenarios = [
            {"repeats_range": VarRange(1, 1), "reduce": ReduceType.SQUEEZE, "result_types": (ResultVar,)},
            {"repeats_range": VarRange(2, None), "reduce": ReduceType.REDUCE, "result_types": (ResultBool,)},
        ]

        for params in scenarios:
            res = self.filter(self.to_bar_ds, **common, **params)
            if res is not None:
                return res
        return None

    def to_bar_ds(self, dataset: xr.Dataset, result_var: Parameter | None = None, **kwargs):
        da = dataset[result_var.name]
        var = result_var.name
        use_holomap = self._use_holomap_for_time(dataset)

        by = kwargs.pop("by", None)
        non_time_dims = [d for d in da.dims if d not in ("repeat", "over_time")]

        if by is None:
            cat_dim_names = [cv.name for cv in self.plt_cnt_cfg.cat_vars]
            x_dim = non_time_dims[0] if non_time_dims else "over_time"
            candidates = [d for d in non_time_dims if d != x_dim and d in cat_dim_names]
            if len(candidates) == 1:
                by = candidates[0]
            elif len(candidates) > 1:
                by = candidates[0]
        else:
            x_dim = non_time_dims[0] if non_time_dims else "over_time"

        title = self.title_from_ds(da, result_var, **kwargs)

        if not non_time_dims and "over_time" in da.dims:
            return None

        if use_holomap:
            def make_bar(ds_t):
                return self._make_bar_fig(ds_t, result_var, x_dim, by, title, **kwargs)
            return self._build_time_holomap(dataset, var, make_bar)

        return self._make_bar_fig(dataset, result_var, x_dim, by, title, **kwargs)

    def _make_bar_fig(self, dataset, result_var, x_dim, by, title, **kwargs):
        var = result_var.name
        da = dataset[var]
        fig = go.Figure()

        if by and by in dataset.dims:
            for ci, val in enumerate(dataset.coords[by].values):
                ds_sel = dataset.sel({by: val})
                x_vals = [str(v) for v in ds_sel.coords[x_dim].values]
                y_vals = ds_sel[var].values.ravel()
                fig.add_trace(go.Bar(
                    x=x_vals, y=y_vals, name=str(val),
                    marker_color=PLOTLY_COLORS[ci % len(PLOTLY_COLORS)],
                ))
            fig.update_layout(barmode="group")
        else:
            x_vals = [str(v) for v in da.coords[x_dim].values] if x_dim in da.coords else []
            y_vals = da.values.ravel()
            fig.add_trace(go.Bar(x=x_vals, y=y_vals, name=var))

        fig.update_layout(
            **self._default_layout(title=title),
            xaxis_title=x_dim,
            yaxis_title=f"{var} [{getattr(result_var, 'units', '')}]",
        )
        return fig
