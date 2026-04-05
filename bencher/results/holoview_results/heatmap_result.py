from __future__ import annotations
import panel as pn
import holoviews as hv
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultFloat
from bencher.results.holoview_results.holoview_result import HoloviewResult, use_tap


class HeatmapResult(HoloviewResult):
    """A class for creating heatmap visualizations from benchmark results.

    Heatmaps are effective for visualizing the relationship between two input variables
    and a result variable by using color intensity to represent the result values.
    This class provides methods for generating interactive heatmaps that can display
    additional information when hovering over or selecting points on the heatmap.
    """

    def to_plot(self, **kwargs) -> pn.panel | None:
        """Generates a heatmap visualization. See ``to_heatmap`` for parameters."""
        return self.to_heatmap(**kwargs)

    def to_heatmap(
        self,
        result_var: Parameter | None = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row | None = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool = use_tap,
        **kwargs,
    ) -> pn.panel | None:
        """Generates a heatmap visualization from benchmark data.

        Args:
            result_var (Parameter, optional): The result variable to plot.
            tap_var: Variables to display when tapping on heatmap points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            tap_container_direction (pn.Column | pn.Row, optional): Layout direction for tap
                containers.
            target_dimension (int, optional): Target dimensionality. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            pn.panel | None: A panel containing the heatmap, or filter match results.
        """
        if tap_var is None:
            tap_var = self.plt_cnt_cfg.panel_vars
        elif not isinstance(tap_var, list):
            tap_var = [tap_var]

        if len(tap_var) == 0 or not use_tap:
            heatmap_cb = self.to_heatmap_ds
        else:
            heatmap_cb = partial(
                self._to_heatmap_tap_ds,
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
            result_types=(ResultFloat,),
            override=override,
            **kwargs,
        )

    def to_heatmap_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> hv.HeatMap | hv.HoloMap | None:
        """Creates a basic heatmap from the provided dataset.

        When over_time is active with multiple time points, creates an hv.HoloMap
        with a slider.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the heatmap options.

        Returns:
            hv.HeatMap | hv.HoloMap | None: A heatmap visualization, or None if
                the dataset has fewer than 2 dimensions.
        """
        if len(dataset.dims) < 2:
            return None

        x = self.bench_cfg.input_vars[0].name
        y = self.bench_cfg.input_vars[1].name
        C = result_var.name
        title = f"Heatmap of {result_var.name}"

        if self._use_holomap_for_time(dataset):

            def make_heatmap(ds_t):
                # Convert to DataFrame so hv.HeatMap gets proper column names;
                # hv.Dataset(xr.Dataset) drops categorical-only dims.
                df = ds_t[C].to_dataframe().reset_index()
                return hv.HeatMap(df, kdims=[x, y], vdims=[C]).opts(
                    cmap="plasma", title=title, xrotation=30, **kwargs
                )

            return self._build_time_holomap(dataset, C, make_heatmap)

        plot = dataset.hvplot.heatmap(
            x=x, y=y, C=C, cmap="plasma", title=title, widget_location="bottom", **kwargs
        )
        return self._apply_opts(plot, xrotation=30)

    def _to_heatmap_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: list[Parameter] | None = None,
        container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row | None = None,
        **kwargs,
    ) -> pn.Row:
        """Creates an interactive heatmap with tap functionality.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The primary result variable to plot.
            result_var_plots (list[Parameter], optional): Additional result variables
                to display when a point is tapped.
            container (pn.pane.panel, optional): Container to display tapped information.
            tap_container_direction (pn.Column | pn.Row, optional): Layout direction for
                tap containers.
            **kwargs: Additional keyword arguments passed to the heatmap options.

        Returns:
            pn.Row: A panel row containing the interactive heatmap and tap info.
        """
        x = self.bench_cfg.input_vars[0].name
        y = self.bench_cfg.input_vars[1].name
        C = result_var.name
        title = f"Heatmap of {result_var.name}"
        df = dataset[C].to_dataframe().reset_index()
        plot = hv.HeatMap(df, kdims=[x, y], vdims=[C]).opts(
            cmap="plasma", title=title, tools=["hover"], xrotation=30, **kwargs
        )
        return self._build_tap_plot(
            plot, dataset, result_var_plots, container, tap_container_direction
        )

    def to_heatmap_tap(
        self,
        result_var: Parameter,
        reduce: ReduceType = ReduceType.AUTO,
        width=800,
        height=800,
        **kwargs,
    ):
        """Creates a tappable heatmap that shows details when tapped.

        Uses ``hv.streams.Tap`` for static click coordinates rather than
        PointerXY hover tracking.

        Args:
            result_var (Parameter): The result variable to plot.
            reduce (ReduceType, optional): How to reduce the data. Defaults to ReduceType.AUTO.
            width (int, optional): Width of the plot in pixels. Defaults to 800.
            height (int, optional): Height of the plot in pixels. Defaults to 800.
            **kwargs: Additional keyword arguments.

        Returns:
            hv.Layout: A layout containing the heatmap and a dynamically updated detail view.
        """
        z = result_var
        color_label = f"{z.name} [{z.units}]"
        htmap = self.to_hv_type(hv.HeatMap, reduce).opts(
            clabel=color_label,
            tools=["hover", "tap"],
            width=width,
            height=height,
            xrotation=30,
        )
        htmap_posxy = hv.streams.Tap(source=htmap, x=0, y=0)

        def tap_plot(x, y):
            kwargs[self.bench_cfg.input_vars[0].name] = x
            kwargs[self.bench_cfg.input_vars[1].name] = y
            return self.get_nearest_holomap(**kwargs).opts(width=width, height=height)

        tap_htmap = hv.DynamicMap(tap_plot, streams=[htmap_posxy])
        return htmap + tap_htmap
