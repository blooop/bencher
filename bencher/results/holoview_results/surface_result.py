from __future__ import annotations

import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


def _da_to_sorted_grid(da: xr.DataArray, x_name: str, y_name: str):
    """Extract sorted x/y coordinate arrays and a 2D z grid from a DataArray."""
    sorted_da = da.sortby([x_name, y_name])
    return (
        sorted_da.coords[x_name].values,
        sorted_da.coords[y_name].values,
        sorted_da.values,
    )


class SurfaceResult(HoloviewResult):
    """3D surface plots using Plotly."""

    def to_plot(self, result_var=None, override=True, **kwargs):
        return self.to_surface(result_var=result_var, override=override, **kwargs)

    def to_surface(self, result_var=None, override=True, target_dimension=2, **kwargs):
        return self.filter(
            self.to_surface_ds,
            float_range=VarRange(2, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(1, None),
            reduce=ReduceType.REDUCE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar,),
            override=override,
            **kwargs,
        )

    def to_surface_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        override: bool = True,
        alpha: float = 0.3,
        width: int = 600,
        height: int = 600,
    ):
        matches_res = PlotFilter(
            float_range=VarRange(2, 2),
            cat_range=VarRange(0, None),
            vector_len=VarRange(1, 1),
            result_vars=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_surface_plotly", override)

        if matches_res.overall:
            x = self.plt_cnt_cfg.float_vars[0]
            y = self.plt_cnt_cfg.float_vars[1]

            mean_da = dataset[result_var.name]
            x_vals, y_vals, z_vals = _da_to_sorted_grid(mean_da, x.name, y.name)

            data = [
                go.Surface(
                    x=x_vals,
                    y=y_vals,
                    z=z_vals,
                    colorscale="Viridis",
                    colorbar=dict(title=f"{result_var.name} [{result_var.units}]"),
                )
            ]

            if self.bench_cfg.repeats > 1:
                std_dev = dataset[f"{result_var.name}_std"]
                for bound, sign in [("upper", 1), ("lower", -1)]:
                    bound_da = mean_da + sign * std_dev
                    _, _, bz = _da_to_sorted_grid(bound_da, x.name, y.name)
                    data.append(
                        go.Surface(
                            x=x_vals,
                            y=y_vals,
                            z=bz,
                            colorscale="Viridis",
                            showscale=False,
                            opacity=alpha,
                            name=bound,
                        )
                    )

            fig = go.Figure(data=data)
            fig.update_layout(
                title=f"{result_var.name} vs ({x.name} and {y.name})",
                width=width,
                height=height,
                margin=dict(t=50, b=50, r=50, l=50),
                scene=dict(
                    xaxis_title=f"{x.name} [{x.units}]",
                    yaxis_title=f"{y.name} [{y.units}]",
                    zaxis_title=f"{result_var.name} [{result_var.units}]",
                ),
            )
            return fig

        return matches_res.to_panel()
