from __future__ import annotations

import plotly.graph_objects as go
import xarray as xr
from param import Parameter

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange, PlotFilter
from bencher.results.holoview_results.holoview_result import HoloviewResult, PLOTLY_COLORS


class ScatterResult(HoloviewResult):
    """Scatter plots using Plotly."""

    def to_plot(self, override: bool = True, **kwargs):
        return self.to_scatter(override=override, **kwargs)

    def to_scatter(self, result_var=None, override: bool = True, **kwargs):
        match_res = PlotFilter(
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_scatter", override=override)
        if match_res.overall:
            return self.filter(
                self._to_scatter_ds,
                float_range=VarRange(0, 0),
                cat_range=VarRange(0, None),
                repeats_range=VarRange(1, 1),
                reduce=ReduceType.SQUEEZE,
                result_var=result_var,
                override=override,
                **kwargs,
            )
        return match_res.to_panel(**kwargs)

    def _to_scatter_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        title = self.title_from_ds(dataset, result_var, **kwargs)
        var = result_var.name
        fig = go.Figure()

        dims = [d for d in dataset.dims if d != "repeat"]
        if not dims:
            # 0D case
            y_vals = dataset[var].values.ravel()
            fig.add_trace(
                go.Scatter(
                    y=y_vals,
                    mode="markers",
                    name=var,
                )
            )
        elif len(dims) == 1:
            x_dim = dims[0]
            x_vals = dataset.coords[x_dim].values
            y_vals = dataset[var].values.ravel()
            fig.add_trace(
                go.Scatter(
                    x=[str(v) for v in x_vals],
                    y=y_vals,
                    mode="markers",
                    name=var,
                )
            )
            fig.update_layout(xaxis_title=x_dim)
        else:
            # Multiple dims: use first as x, second as color
            x_dim = dims[0]
            by_dim = dims[1] if len(dims) > 1 else None
            if by_dim:
                for ci, val in enumerate(dataset.coords[by_dim].values):
                    ds_sel = dataset.sel({by_dim: val})
                    x_vals = ds_sel.coords[x_dim].values
                    y_vals = ds_sel[var].values.ravel()
                    fig.add_trace(
                        go.Scatter(
                            x=[str(v) for v in x_vals],
                            y=y_vals,
                            mode="markers",
                            name=str(val),
                            marker=dict(color=PLOTLY_COLORS[ci % len(PLOTLY_COLORS)]),
                        )
                    )
            fig.update_layout(xaxis_title=x_dim)

        fig.update_layout(
            **self._default_layout(title=title),
            yaxis_title=f"{var} [{getattr(result_var, 'units', '')}]",
        )
        return fig
