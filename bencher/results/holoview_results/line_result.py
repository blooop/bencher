from __future__ import annotations
from typing import List, Optional
import panel as pn
import holoviews as hv
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.utils import (
    get_nearest_coords1D,
)
from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


class LineResult(HoloviewResult):
    """A class for creating line plot visualizations from benchmark results.

    Line plots are effective for visualizing trends in data over a continuous variable.
    This class provides methods to generate interactive line plots from benchmark data,
    with options for adding interactive tap functionality to display detailed information
    about specific data points.
    """

    def to_plot(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a line plot from benchmark data.

        This is a convenience method that calls to_line() with the same parameters.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            tap_var: Variables to display when tapping on line plot points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            target_dimension (int, optional): Target dimensionality for the plot. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the line plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.to_line(
            result_var=result_var,
            tap_var=tap_var,
            tap_container=tap_container,
            target_dimension=target_dimension,
            override=override,
            use_tap=use_tap,
            **kwargs,
        )

    def to_line(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        target_dimension: int = 2,
        override: bool = True,
        use_tap: bool = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a line plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a line plot
        and then passes the filtered data to the appropriate rendering method. If tap
        functionality is enabled, it will create an interactive line plot that displays
        additional information when data points are selected.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            tap_var: Variables to display when tapping on line plot points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            target_dimension (int, optional): Target dimensionality for the plot. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the line plot if data is appropriate,
                              otherwise returns filter match results.
        """
        if tap_var is None:
            tap_var = self.plt_cnt_cfg.panel_vars
        elif not isinstance(tap_var, list):
            tap_var = [tap_var]

        if len(tap_var) == 0 or self.plt_cnt_cfg.inputs_cnt > 1 or not use_tap:
            line_cb = self.to_line_ds
        else:
            line_cb = partial(
                self.to_line_tap_ds, result_var_plots=tap_var, container=tap_container
            )

        return self.filter(
            line_cb,
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            panel_range=VarRange(0, None),
            reduce=ReduceType.SQUEEZE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar),
            override=override,
            **kwargs,
        )

    def to_line_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        """Creates a basic line plot from the provided dataset.

        Given a filtered dataset, this method generates a line plot visualization showing
        the relationship between a continuous input variable and the result variable.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the line plot options.

        Returns:
            hvplot.element.Curve: A line plot visualization of the benchmark data.
        """
        x = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        time_widget_args = self.time_widget(title)
        return da_plot.hvplot.line(x=x, by=by, **time_widget_args, **kwargs)

    def to_line_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: List[Parameter] = None,
        container: pn.pane.panel = pn.pane.panel,
        **kwargs,
    ) -> pn.Row:
        """Creates an interactive line plot with tap functionality.

        This method generates a line plot with interactive hover and tap functionality that
        displays additional information about selected points in separate containers.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The primary result variable to plot in the line plot.
            result_var_plots (List[Parameter], optional): Additional result variables to display when a point is tapped.
            container (pn.pane.panel, optional): Container to display tapped information.
            **kwargs: Additional keyword arguments passed to the line plot options.

        Returns:
            pn.Row: A panel row containing the interactive line plot and containers for tapped information.
        """
        htmap = self.to_line_ds(dataset, result_var).opts(tools=["hover"], **kwargs)
        result_var_plots, cont_instances = self.setup_results_and_containers(
            result_var_plots, container
        )
        title = pn.pane.Markdown("Selected: None")

        state = dict(x=None, y=None, update=False)

        def tap_plot_line(x, y):  # pragma: no cover
            # print(f"{x},{y}")
            # print(dataset)

            # xv = self.bench_cfg.input_vars[0].name
            # yv = self.bench_cfg.input_vars[1].name

            # x_nearest_new = get_nearest_coords1D(
            #     x, dataset.coords[self.bench_cfg.input_vars[0].name].data
            # )
            # y_nearest_new = get_nearest_coords1D(
            #     y, dataset.coords[self.bench_cfg.input_vars[1].name].data
            # )

            # kwargs = {xv: x, yv: y}

            # nearest = get_nearest_coords(dataset, **kwargs)
            # print(nearest)

            x_nearest_new = get_nearest_coords1D(
                x, dataset.coords[self.bench_cfg.input_vars[0].name].data
            )

            if x_nearest_new != state["x"]:
                state["x"] = x_nearest_new
                state["update"] = True

            if self.plt_cnt_cfg.inputs_cnt > 1:
                y_nearest_new = get_nearest_coords1D(
                    y, dataset.coords[self.bench_cfg.input_vars[1].name].data
                )
                if y_nearest_new != state["y"]:
                    state["y"] = y_nearest_new
                    state["update"] = True

            if state["update"]:
                kdims = {}
                kdims[self.bench_cfg.input_vars[0].name] = state["x"]
                if self.plt_cnt_cfg.inputs_cnt > 1:
                    kdims[self.bench_cfg.input_vars[1].name] = state["y"]

                if hasattr(htmap, "current_key"):
                    for d, k in zip(htmap.kdims, htmap.current_key):
                        kdims[d.name] = k
                for rv, cont in zip(result_var_plots, cont_instances):
                    ds = dataset[rv.name]
                    val = ds.sel(**kdims)
                    item = self.zero_dim_da_to_val(val)
                    title.object = "Selected: " + ", ".join([f"{k}:{v}" for k, v in kdims.items()])
                    cont.object = item
                    if hasattr(cont, "autoplay"):  # container is a video, set to autoplay
                        cont.paused = False
                        cont.time = 0
                        cont.loop = True
                        cont.autoplay = True
                state["update"] = False

        def on_exit(x, y):  # pragma: no cover # pylint: disable=unused-argument
            state["update"] = True

        htmap_posxy = hv.streams.PointerXY(source=htmap)
        htmap_posxy.add_subscriber(tap_plot_line)
        ls = hv.streams.MouseLeave(source=htmap)
        ls.add_subscriber(on_exit)
        bound_plot = pn.Column(title, *cont_instances)
        return pn.Row(htmap, bound_plot)
