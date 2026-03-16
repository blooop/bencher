from __future__ import annotations
import panel as pn
from param import Parameter
import plotly.graph_objs as go
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


def _da_to_sorted_grid(da: xr.DataArray, x_name: str, y_name: str):
    """Extract sorted x/y coordinate arrays and a 2D z grid from a DataArray.

    Sorts the DataArray along both axes so the resulting grid has monotonically
    increasing x and y values, which plotly requires for correct surface rendering.
    """
    sorted_da = da.sortby([x_name, y_name])
    return (
        sorted_da.coords[x_name].values,
        sorted_da.coords[y_name].values,
        sorted_da.values,
    )


class SurfaceResult(HoloviewResult):
    """A class for creating 3D surface plots from benchmark results.

    This class provides methods to visualize benchmark data as 3D surface plots,
    which are useful for showing relationships between two input variables and
    a result variable. Surface plots can also display standard deviation bounds
    when benchmark runs include multiple repetitions.
    """

    def to_plot(
        self, result_var: Parameter | None = None, override: bool = True, **kwargs
    ) -> pn.pane.Pane | None:
        """Generates a 3D surface plot from benchmark data.

        This is a convenience method that calls to_surface() with the same parameters.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            pn.pane.Pane | None: A panel containing the surface plot if data is appropriate,
                                   otherwise returns filter match results.
        """
        return self.to_surface(result_var=result_var, override=override, **kwargs)

    def to_surface(
        self,
        result_var: Parameter | None = None,
        override: bool = True,
        target_dimension: int = 2,
        **kwargs,
    ) -> pn.pane.Pane | None:
        """Generates a 3D surface plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a surface plot
        and then passes the filtered data to to_surface_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 2.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            pn.pane.Pane | None: A panel containing the surface plot if data is appropriate,
                                   otherwise returns filter match results.
        """
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
    ) -> pn.panel | None:
        """Creates a 3D surface plot from the provided dataset.

        Uses plotly directly (like VolumeResult) to avoid HoloViews backend
        contamination issues while ensuring reliable 3D rendering. Coordinates
        are sorted to guarantee monotonic x/y grids for plotly.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            alpha (float, optional): The transparency for std-dev surfaces. Defaults to 0.3.
            width (int, optional): Plot width in pixels. Defaults to 600.
            height (int, optional): Plot height in pixels. Defaults to 600.

        Returns:
            pn.panel | None: A panel containing the surface plot if data matches criteria,
                               otherwise returns filter match results.
        """
        matches_res = PlotFilter(
            float_range=VarRange(2, 2),
            cat_range=VarRange(0, None),
            vector_len=VarRange(1, 1),
            result_vars=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_surface_hv", override)
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

            layout = go.Layout(
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

            fig = dict(data=data, layout=layout)
            return pn.pane.Plotly(fig, name="surface_plotly")

        return matches_res.to_panel()
