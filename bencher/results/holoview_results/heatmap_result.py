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
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


class HeatmapResult(HoloviewResult):
    """A class for creating heatmap visualizations from benchmark results.

    Heatmaps are effective for visualizing the relationship between two input variables
    and a result variable by using color intensity to represent the result values.
    This class provides methods for generating interactive heatmaps that can display
    additional information when hovering over or selecting points on the heatmap.
    """

    def to_plot(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a heatmap visualization from benchmark data.

        This is a convenience method that calls to_heatmap() with the same parameters.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            tap_var: Variables to display when tapping on heatmap points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            tap_container_direction (pn.Column | pn.Row, optional): Layout direction for the tap container.
            target_dimension (int, optional): Target dimensionality for the plot. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the heatmap if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.to_heatmap(
            result_var=result_var,
            tap_var=tap_var,
            tap_container=tap_container,
            tap_container_direction=tap_container_direction,
            target_dimension=target_dimension,
            override=override,
            use_tap=use_tap,
            **kwargs,
        )

    def to_heatmap(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a heatmap visualization from benchmark data.

        This method applies filters to ensure the data is appropriate for a heatmap
        and then passes the filtered data to the appropriate rendering method. If tap
        functionality is enabled, it will create an interactive heatmap that displays
        additional information when data points are selected.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            tap_var: Variables to display when tapping on heatmap points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            tap_container_direction (pn.Column | pn.Row, optional): Layout direction for the tap container.
            target_dimension (int, optional): Target dimensionality for the plot. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the heatmap if data is appropriate,
                              otherwise returns filter match results.
        """
        if tap_var is None:
            tap_var = self.plt_cnt_cfg.panel_vars
        elif not isinstance(tap_var, list):
            tap_var = [tap_var]

        if len(tap_var) == 0 or not use_tap:
            heatmap_cb = self.to_heatmap_ds
        else:
            heatmap_cb = partial(
                self.to_heatmap_container_tap_ds,
                result_var_plots=tap_var,
                container=tap_container,
                tap_container_direction=tap_container_direction,
            )

        return self.filter(
            heatmap_cb,
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(2, None),
            panel_range=VarRange(0, None),
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar),
            override=override,
            **kwargs,
        )

    def to_heatmap_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> Optional[hv.HeatMap]:
        """Creates a basic heatmap from the provided dataset.

        Given a filtered dataset, this method generates a heatmap visualization showing
        the relationship between two input variables and a result variable using color intensity.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the heatmap options.

        Returns:
            Optional[hv.HeatMap]: A heatmap visualization if the dataset has at least 2 dimensions,
                                 otherwise returns None.
        """
        if len(dataset.dims) >= 2:
            x = self.bench_cfg.input_vars[0].name
            y = self.bench_cfg.input_vars[1].name
            C = result_var.name
            title = f"Heatmap of {result_var.name}"
            time_args = self.time_widget(title)
            return dataset.hvplot.heatmap(x=x, y=y, C=C, cmap="plasma", **time_args, **kwargs)
        return None

    def to_heatmap_container_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: List[Parameter] = None,
        container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row = None,
        **kwargs,
    ) -> pn.Row:
        """Creates an interactive heatmap with tap functionality.

        This method generates a heatmap with interactive tap functionality that displays
        additional information about selected points in separate containers.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The primary result variable to plot in the heatmap.
            result_var_plots (List[Parameter], optional): Additional result variables to display when a point is tapped.
            container (pn.pane.panel, optional): Container to display tapped information.
            tap_container_direction (pn.Column | pn.Row, optional): Layout direction for the tap containers.
            **kwargs: Additional keyword arguments passed to the heatmap options.

        Returns:
            pn.Row: A panel row containing the interactive heatmap and containers for tapped information.
        """
        htmap = self.to_heatmap_ds(dataset, result_var).opts(tools=["hover"], **kwargs)
        result_var_plots, cont_instances = self.setup_results_and_containers(
            result_var_plots, container
        )
        title = pn.pane.Markdown("Selected: None")

        state = dict(x=None, y=None, update=False)

        def tap_plot_heatmap(x, y):  # pragma: no cover
            # print(f"moved {x}{y}")
            x_nearest_new = get_nearest_coords1D(
                x, dataset.coords[self.bench_cfg.input_vars[0].name].data
            )
            y_nearest_new = get_nearest_coords1D(
                y, dataset.coords[self.bench_cfg.input_vars[1].name].data
            )

            # xv = self.bench_cfg.input_vars[0].name
            # yv = self.bench_cfg.input_vars[1].name
            # nearest = get_nearest_coords(dataset, **{xv: x, yv: y})
            # print(nearest)
            # print(x_nearest_new,y_nearest_new)

            if x_nearest_new != state["x"]:
                state["x"] = x_nearest_new
                state["update"] = True
            if y_nearest_new != state["y"]:
                state["y"] = y_nearest_new
                state["update"] = True

            if state["update"]:
                kdims = {}
                kdims[self.bench_cfg.input_vars[0].name] = state["x"]
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
        htmap_posxy.add_subscriber(tap_plot_heatmap)
        ls = hv.streams.MouseLeave(source=htmap)
        ls.add_subscriber(on_exit)

        if tap_container_direction is None:
            tap_container_direction = pn.Column
        bound_plot = tap_container_direction(*cont_instances)

        return pn.Row(htmap, pn.Column(title, bound_plot))

    def to_heatmap_single(
        self,
        result_var: Parameter,
        override: bool = True,
        reduce: ReduceType = ReduceType.AUTO,
        **kwargs,
    ) -> hv.HeatMap:
        """Creates a single heatmap from the result variable.

        This method creates a heatmap directly from the benchmark results dataset without
        applying the standard filtering pipeline.

        Args:
            result_var (Parameter): The result variable to plot.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            reduce (ReduceType, optional): How to reduce the data. Defaults to ReduceType.AUTO.
            **kwargs: Additional keyword arguments passed to the heatmap options.

        Returns:
            hv.HeatMap: A heatmap visualization if data matches criteria,
                       otherwise returns filter match results.
        """
        matches_res = PlotFilter(
            float_range=VarRange(2, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(1, None),
        ).matches_result(self.plt_cnt_cfg, "to_heatmap", override)
        if matches_res.overall:
            z = result_var
            title = f"{z.name} vs ("

            for iv in self.bench_cfg.input_vars:
                title += f" vs {iv.name}"
            title += ")"

            color_label = f"{z.name} [{z.units}]"

            return self.to_hv_type(hv.HeatMap, reduce).opts(clabel=color_label, **kwargs)
        return matches_res.to_panel()

    def to_heatmap_tap(
        self,
        result_var: Parameter,
        reduce: ReduceType = ReduceType.AUTO,
        width=800,
        height=800,
        **kwargs,
    ):
        """Creates a tappable heatmap that shows details when tapped.

        This method generates a heatmap with tap functionality that displays
        additional visualizations when a point is selected.

        Args:
            result_var (Parameter): The result variable to plot.
            reduce (ReduceType, optional): How to reduce the data. Defaults to ReduceType.AUTO.
            width (int, optional): Width of the plot in pixels. Defaults to 800.
            height (int, optional): Height of the plot in pixels. Defaults to 800.
            **kwargs: Additional keyword arguments.

        Returns:
            hv.Layout: A layout containing both the heatmap and the dynamically updated detail view.
        """
        htmap = self.to_heatmap_single(result_var, reduce).opts(
            tools=["hover", "tap"], width=width, height=height
        )
        htmap_posxy = hv.streams.Tap(source=htmap, x=0, y=0)

        def tap_plot(x, y):
            kwargs[self.bench_cfg.input_vars[0].name] = x
            kwargs[self.bench_cfg.input_vars[1].name] = y
            return self.get_nearest_holomap(**kwargs).opts(width=width, height=height)

        tap_htmap = hv.DynamicMap(tap_plot, streams=[htmap_posxy])
        return htmap + tap_htmap
