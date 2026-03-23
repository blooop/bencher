from __future__ import annotations
import panel as pn
import holoviews as hv
import numpy as np
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.utils import (
    hmap_canonical_input,
    get_nearest_coords,
    listify,
)
from bencher.results.video_result import VideoResult
from bencher.results.bench_result_base import ReduceType

from bencher.variables.results import ResultVar, ResultImage, ResultVideo

hv.extension("bokeh", "plotly")

# Flag to enable or disable tap tool functionality in visualizations
use_tap = True

_AGG_TITLE = "All Time Points (aggregated)"


class HoloviewResult(VideoResult):
    @staticmethod
    def set_default_opts(width: int = 600, height: int = 600) -> dict:
        """Set default options for HoloViews visualizations.

        Args:
            width (int, optional): Default width for visualizations. Defaults to 600.
            height (int, optional): Default height for visualizations. Defaults to 600.

        Returns:
            dict: Dictionary containing width, height, and tools settings.
        """
        width_height = {"width": width, "height": height, "tools": ["hover"]}
        hv.opts.defaults(
            hv.opts.Curve(**width_height),
            hv.opts.Points(**width_height),
            hv.opts.Bars(**width_height),
            hv.opts.Scatter(**width_height),
            hv.opts.BoxWhisker(**width_height),
            hv.opts.Violin(**width_height),
            hv.opts.HeatMap(cmap="plasma", **width_height, colorbar=True),
            # hv.opts.Surface(**width_heigh),
            hv.opts.GridSpace(plot_size=400),
        )
        return width_height

    def to_hv_type(self, hv_type: type, reduce: ReduceType = ReduceType.AUTO, **kwargs) -> hv.Chart:
        """Convert the dataset to a specific HoloViews visualization type.

        Args:
            hv_type (type): The HoloViews chart type to convert to (e.g., hv.Points, hv.Curve).
            reduce (ReduceType, optional): How to reduce dataset dimensions. Defaults to ReduceType.AUTO.
            **kwargs: Additional parameters to pass to the chart constructor.

        Returns:
            hv.Chart: A HoloViews chart of the specified type.
        """
        return self.to_hv_dataset(reduce).to(hv_type, **kwargs)

    def overlay_plots(self, plot_callback: callable) -> hv.Overlay | pn.Row | None:
        """Create an overlay of plots by applying a callback to each result variable.

        Args:
            plot_callback (callable): Function to apply to each result variable to create a plot.

        Returns:
            hv.Overlay | pn.Row | None: An overlay of plots or Row of plots, or None if no results.
        """
        results = []
        markdown_results = pn.Row()
        for rv in self.bench_cfg.result_vars:
            res = plot_callback(rv)
            if res is not None:
                if isinstance(res, pn.pane.Markdown):
                    markdown_results.append(res)
                else:
                    results.append(res)
        if len(results) > 0:
            overlay = hv.Overlay(results).collate()
            if len(markdown_results) == 0:
                return overlay
            return pn.Row(overlay, markdown_results)
        if len(markdown_results) > 0:
            return markdown_results
        return None

    def layout_plots(self, plot_callback: callable) -> hv.Layout | None:
        """Create a layout of plots by applying a callback to each result variable.

        Args:
            plot_callback (callable): Function to apply to each result variable to create a plot.

        Returns:
            hv.Layout | None: A layout of plots or None if no results.
        """
        if len(self.bench_cfg.result_vars) > 0:
            pt = hv.Layout()
            got_results = False
            for rv in self.bench_cfg.result_vars:
                res = plot_callback(rv)
                if res is not None:
                    got_results = True
                    pt += plot_callback(rv)
            return pt if got_results else None
        return plot_callback(self.bench_cfg.result_vars[0])

    def time_widget(self, title: str) -> dict:
        """Create widget configuration for time-based visualizations.

        Args:
            title (str): Title for the widget.

        Returns:
            dict: Widget configuration dictionary with title.
        """
        return {"title": title}

    def _use_holomap_for_time(self, dataset: xr.Dataset) -> bool:
        """Check whether over_time should be rendered via an hv.HoloMap slider.

        Returns True when over_time is active and the dataset has >1 time points.
        """
        return (
            self.bench_cfg.over_time
            and "over_time" in dataset.dims
            and dataset.sizes["over_time"] > 1
        )

    @staticmethod
    def _apply_opts(plot, **opts_kwargs):
        """Apply .opts() to a plot, handling panel.pane.HoloViews wrappers.

        When hvplot is called with widget_location, it returns a panel pane
        whose underlying .object is the actual holoviews element.
        """
        if hasattr(plot, "opts"):
            return plot.opts(**opts_kwargs)
        if hasattr(plot, "object") and hasattr(plot.object, "opts"):
            plot.object = plot.object.opts(**opts_kwargs)
        return plot

    @staticmethod
    def _over_time_kdims() -> list:
        """Return the kdim list for over_time HoloMaps."""
        return ["over_time"]

    @staticmethod
    def _holomap_with_slider_bottom(hvobj, widgets=None):
        """Wrap a HoloViews object so any scrubber/slider appears below the plot.

        ``pn.pane.HoloViews(holomap, widget_location="bottom")`` does not
        embed correctly in static HTML (the widget is lost).  Instead we
        let Panel auto-create the widget via ``pn.panel(hvobj)`` (which
        produces a ``Row(plot, widget_box)``), then rearrange into a
        ``Column(plot, widget_box)`` so the slider sits underneath.

        Force ``DiscreteSlider`` for the *over_time* dimension so that
        string-based ``TimeEvent`` coordinates get a slider instead of
        the default dropdown ``Select`` widget.

        Safe to call on any HoloViews object; if no widgets are produced
        the original object is returned unchanged.

        The slider defaults to the most recent (last) time point by
        setting the widget value in Python.  Panel's embed system computes
        JSON patches relative to this default, so every other position
        gets a valid patch and the last position is the initial state.
        """
        if widgets is None:
            widgets = {"over_time": pn.widgets.DiscreteSlider}
        row = pn.panel(hvobj, widgets=widgets)
        if not isinstance(row, pn.Row) or len(row) < 2:
            return hvobj
        widget_box = row[1]
        widget_box.align = ("start", "start")

        # Set the over_time slider to the last (most recent) time point.
        for w in widget_box:
            if hasattr(w, "name") and w.name == "over_time" and hasattr(w, "options") and w.options:
                opts = w.options.values() if isinstance(w.options, dict) else w.options
                opts = list(opts)
                if len(opts) > 1:
                    w.value = opts[-1]
                break

        return pn.Column(row[0], widget_box)

    def _build_curve_overlay(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> hv.Overlay:
        """Build a Curve (+ optional Spread) overlay for a single time slice or aggregated data.

        When ``_std`` exists in the dataset the spread band is rendered
        automatically.  This is used by both the curve renderer and the
        line renderer (for aggregated data that gained ``_std`` from
        ``_mean_over_time``).

        Performance: avoids ``to_dataframe()`` when there are no categorical
        groupby dimensions by constructing ``hv.Dataset`` directly from the
        xarray Dataset.  The heavier DataFrame path is only used when manual
        groupby is required.
        """
        var = result_var.name
        std_var = f"{var}_std"
        has_spread = std_var in dataset.data_vars
        title = self.title_from_ds(dataset, result_var, **kwargs)

        float_names = [fv.name for fv in self.plt_cnt_cfg.float_vars]
        ds_dims = list(dataset.dims)
        kdims = [d for d in ds_dims if d in float_names] or ds_dims[:1]
        groupby = [d for d in ds_dims if d not in kdims]

        vdims = [var, std_var] if has_spread else [var]

        if not groupby:
            # Fast path: build hv.Dataset directly from xarray (no DataFrame conversion)
            hvds = hv.Dataset(dataset, kdims=kdims, vdims=vdims)
            pt = hv.Overlay()
            pt *= hv.Curve(hvds, kdims=kdims, vdims=var, label=var).opts(
                title=title, xrotation=30, **kwargs
            )
            if has_spread:
                pt *= hv.Spread(hvds, kdims=kdims, vdims=[var, std_var])
            return pt.opts(legend_position="right")

        # Groupby path: DataFrame needed for manual group iteration
        df = dataset.to_dataframe().reset_index()
        pt = hv.Overlay()
        for key, group_df in df.groupby(groupby):
            label = str(key) if not isinstance(key, tuple) else ", ".join(str(k) for k in key)
            group_hvds = hv.Dataset(group_df, kdims=kdims, vdims=vdims)
            pt *= hv.Curve(group_hvds, kdims=kdims, vdims=var, label=label).opts(
                xrotation=30, **kwargs
            )
            if has_spread:
                pt *= hv.Spread(group_hvds, kdims=kdims, vdims=[var, std_var])
        return pt.opts(title=title, legend_position="right")

    @staticmethod
    def _mean_over_time(dataset, result_var_name):
        """Average a dataset across all time points.

        Always produces a ``_std`` variable so that downstream renderers
        (e.g. curve spread, error bars) can visualise the aggregation
        uncertainty.  When a per-time-point ``_std`` already exists the
        pooled standard deviation is computed via the law of total
        variance; otherwise the standard deviation of the means across
        time points is used.
        """
        std_var = f"{result_var_name}_std"
        new_ds = dataset.mean(dim="over_time")
        var_of_means = dataset[result_var_name].var(dim="over_time")
        if std_var in dataset.data_vars:
            mean_of_vars = (dataset[std_var] ** 2).mean(dim="over_time")
            new_ds[std_var] = (mean_of_vars + var_of_means) ** 0.5
        else:
            new_ds[std_var] = var_of_means**0.5
        return new_ds

    @staticmethod
    def subsample_indices(n, max_points):
        """Return evenly-spaced indices into a length-*n* array.

        Always includes the first and last index.  When *max_points* is
        ``None`` or >= *n*, returns ``range(n)`` (no subsampling).
        """
        if max_points is None or n <= max_points:
            return range(n)
        return np.unique(np.linspace(0, n - 1, max_points, dtype=int)).tolist()

    @staticmethod
    def _strip_std_vars(dataset):
        """Remove ``_std`` variables from a dataset.

        Per-time-point slices carry within-repeat ``_std`` which adds
        Spread-band rendering cost without much analytical value.
        Stripping them lets downstream renderers skip Spread bands
        automatically, reducing per-slider-position render cost.
        """
        std_vars = [v for v in dataset.data_vars if v.endswith("_std")]
        return dataset.drop_vars(std_vars) if std_vars else dataset

    def _build_time_holomap(self, dataset, result_var_name, make_plot_fn):
        """Build per-time-point HoloMap + optional aggregated plot.

        ``make_plot_fn`` receives a Dataset *without* the ``over_time``
        dimension.  The aggregated dataset produced by ``_mean_over_time``
        always contains a ``_std`` variable; callbacks that are
        ``_std``-aware (e.g. delegating to ``_build_curve_overlay``) will
        automatically render spread bands on the aggregated tab.

        Per-time-point slices have ``_std`` variables stripped so that
        Spread bands are not rendered on individual slider positions,
        reducing rendering overhead.

        When ``bench_cfg.max_slider_points`` is set, only that many
        evenly-spaced time points are rendered for the slider (first and
        last always included).  The aggregated tab still uses all data.

        When ``bench_cfg.show_aggregated_time_tab`` is ``False``, the
        aggregation is skipped entirely for faster rendering.
        """
        times = dataset.coords["over_time"].values
        n_time = len(times)

        slider_indices = self.subsample_indices(n_time, self.bench_cfg.max_slider_points)

        kdims = self._over_time_kdims()
        holomap = hv.HoloMap(kdims=kdims)

        for idx in slider_indices:
            t = times[idx]
            ds_t = self._strip_std_vars(dataset.sel(over_time=t))
            holomap[t] = make_plot_fn(ds_t)

        slider_pane = self._holomap_with_slider_bottom(holomap)

        if n_time > 1 and self.bench_cfg.show_aggregated_time_tab:
            ds_agg = self._mean_over_time(dataset, result_var_name)
            agg_plot = make_plot_fn(ds_agg)
            return pn.Tabs(
                ("Per Time Point", slider_pane),
                (_AGG_TITLE, pn.Column(agg_plot)),
            )

        return slider_pane

    def _build_time_holomap_raw(self, da, make_plot_fn):
        """Build per-time-point HoloMap + optional aggregated plot for distributions.

        *make_plot_fn* receives a DataArray that **retains** the ``over_time``
        dimension (a single-element slice for per-time-point entries, or the
        full array for the aggregated tab).  Callers should flatten via
        ``.to_dataframe().reset_index()`` or equivalent.

        Respects ``bench_cfg.max_slider_points`` and
        ``bench_cfg.show_aggregated_time_tab``.
        """
        times = da.coords["over_time"].values
        n_time = len(times)

        slider_indices = self.subsample_indices(n_time, self.bench_cfg.max_slider_points)

        kdims = self._over_time_kdims()
        holomap = hv.HoloMap(kdims=kdims)

        for idx in slider_indices:
            t = times[idx]
            da_t = da.isel(over_time=slice(idx, idx + 1))
            holomap[t] = make_plot_fn(da_t)

        slider_pane = self._holomap_with_slider_bottom(holomap)

        if n_time > 1 and self.bench_cfg.show_aggregated_time_tab:
            agg_plot = make_plot_fn(da)
            return pn.Tabs(
                ("Per Time Point", slider_pane),
                (_AGG_TITLE, pn.Column(agg_plot)),
            )

        return slider_pane

    def hv_container_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        container: hv.Chart | None = None,
        **kwargs,
    ) -> hv.Chart:
        """Convert an xarray Dataset to a HoloViews container for a specific result variable.

        Args:
            dataset (xr.Dataset): The xarray Dataset containing the data.
            result_var (Parameter): The result variable to visualize.
            container (hv.Chart, optional): The HoloViews container type to use. Defaults to None.
            **kwargs: Additional options to pass to the chart's opts() method.

        Returns:
            hv.Chart: A HoloViews chart containing the visualization.
        """
        return hv.Dataset(dataset[result_var.name]).to(container).opts(**kwargs)

    def to_hv_container(
        self,
        container: pn.pane.panel,
        reduce_type: ReduceType = ReduceType.AUTO,
        target_dimension: int = 2,
        result_var: Parameter | None = None,
        result_types: tuple | None = (ResultVar,),
        **kwargs,
    ) -> pn.pane.panel | None:
        """Convert the data to a HoloViews container with specified dimensions and options.

        Args:
            container (pn.pane.panel): The panel container type to use.
            reduce_type (ReduceType, optional): How to reduce the dataset dimensions. Defaults to ReduceType.AUTO.
            target_dimension (int, optional): Target dimension for the visualization. Defaults to 2.
            result_var (Parameter, optional): Specific result variable to visualize. Defaults to None.
            result_types (tuple, optional): Types of result variables to include. Defaults to (ResultVar).
            **kwargs: Additional visualization options.

        Returns:
            pn.pane.panel | None: A panel containing the visualization, or None if no valid results.
        """
        return self.map_plot_panes(
            partial(self.hv_container_ds, container=container),
            hv_dataset=self.to_hv_dataset(reduce_type),
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=result_types,
            **kwargs,
        )

    def result_var_to_container(self, result_var: Parameter) -> type:
        """Determine the appropriate container type for a given result variable.

        Args:
            result_var (Parameter): The result variable to find a container for.

        Returns:
            type: The appropriate panel container type (PNG, Video, or Column).
        """
        if isinstance(result_var, ResultImage):
            return pn.pane.PNG
        return pn.pane.Video if isinstance(result_var, ResultVideo) else pn.Column

    def setup_results_and_containers(
        self,
        result_var_plots: Parameter | list[Parameter],
        container: type | list[type] | None = None,
        **kwargs,
    ) -> tuple[list[Parameter], list[pn.pane.panel]]:
        """Set up appropriate containers for result variables.

        Args:
            result_var_plots (Parameter | list[Parameter]): Result variables to visualize.
            container (type | list[type], optional): Container types to use. Defaults to None.
            **kwargs: Additional options to pass to the container constructors.

        Returns:
            tuple[list[Parameter], list[pn.pane.panel]]: Tuple containing:
                - List of result variables
                - List of initialized container instances
        """
        result_var_plots = listify(result_var_plots)
        if container is None:
            containers = [self.result_var_to_container(rv) for rv in result_var_plots]
        else:
            containers = listify(container)

        cont_instances = [c(**kwargs) if c is not None else None for c in containers]
        return result_var_plots, cont_instances

    def to_error_bar(self, result_var: Parameter | str | None = None, **kwargs) -> hv.Bars:
        """Convert the dataset to an ErrorBars visualization for a specific result variable.

        Args:
            result_var (Parameter | str, optional): Result variable to visualize. Defaults to None.
            **kwargs: Additional options for dataset reduction.

        Returns:
            hv.Bars: A HoloViews ErrorBars object showing error ranges.
        """
        return self.to_hv_dataset(ReduceType.REDUCE, result_var=result_var, **kwargs).to(
            hv.ErrorBars
        )

    def to_points(self, reduce: ReduceType = ReduceType.AUTO) -> hv.Points:
        """Convert the dataset to a Points visualization with optional error bars.

        Args:
            reduce (ReduceType, optional): How to reduce the dataset dimensions. Defaults to ReduceType.AUTO.

        Returns:
            hv.Points: A HoloViews Points object, potentially with ErrorBars if reduction is applied.
        """
        ds = self.to_hv_dataset(reduce)
        pt = ds.to(hv.Points)
        # if reduce:
        # pt *= ds.to(hv.ErrorBars)
        return pt

    def to_nd_layout(self, hmap_name: str) -> hv.NdLayout:
        """Convert a HoloMap to an NdLayout for multi-dimensional visualization.

        Args:
            hmap_name (str): Name of the HoloMap to convert.

        Returns:
            hv.NdLayout: A HoloViews NdLayout object with the visualization.
        """
        return hv.NdLayout(self.get_hmap(hmap_name), kdims=self.bench_cfg.hmap_kdims).opts(
            shared_axes=False, shared_datasource=False
        )

    def to_holomap(self, name: str | None = None) -> hv.HoloMap:
        """Convert an NdLayout to a HoloMap for animated/interactive visualization.

        Args:
            name (str, optional): Name of the HoloMap to use. Defaults to None.

        Returns:
            hv.HoloMap: A HoloViews HoloMap object with the visualization.
        """
        return hv.HoloMap(self.to_nd_layout(name)).opts(shared_axes=False)

    def to_holomap_list(self, hmap_names: list[str] | None = None) -> pn.Column:
        """Create a column of HoloMaps from multiple named maps.

        Args:
            hmap_names (list[str], optional): list of HoloMap names to include.
                If None, uses all result_hmaps. Defaults to None.

        Returns:
            pn.Column: A panel Column containing multiple HoloMaps.
        """
        if hmap_names is None:
            hmap_names = [i.name for i in self.result_hmaps]
        col = pn.Column()
        for name in hmap_names:
            self.to_holomap(name)
        return col

    def get_nearest_holomap(self, name: str | None = None, **kwargs) -> hv.HoloMap:
        """Get the HoloMap element closest to the specified coordinates.

        Args:
            name (str, optional): Name of the HoloMap to use. Defaults to None.
            **kwargs: Coordinate values to find nearest match for.

        Returns:
            hv.HoloMap: The nearest matching HoloMap element.
        """
        canonical_inp = hmap_canonical_input(
            get_nearest_coords(self.ds, collapse_list=True, **kwargs)
        )
        return self.get_hmap(name)[canonical_inp].opts(framewise=True)

    def to_dynamic_map(self, name: str | None = None) -> hv.DynamicMap:
        """Create a DynamicMap from the HoloMap dictionary.

        Uses the values stored in the holomap dictionary to populate a dynamic map.
        This is much faster than passing the holomap to a holomap object as the
        values are calculated on the fly.

        Args:
            name (str, optional): Name of the HoloMap to use. Defaults to None.

        Returns:
            hv.DynamicMap: A HoloViews DynamicMap for interactive visualization.
        """

        def cb(**kwargs):
            return self.get_hmap(name)[hmap_canonical_input(kwargs)].opts(
                framewise=True, shared_axes=False
            )

        kdims = []
        for i in self.bench_cfg.input_vars + [self.bench_cfg.iv_repeat]:
            kdims.append(i.as_dim(compute_values=True))

        return hv.DynamicMap(cb, kdims=kdims)

    def to_grid(self, inputs: list[str] | None = None) -> hv.GridSpace:
        """Create a grid visualization from a HoloMap.

        Args:
            inputs (list[str], optional): Input variable names to use for the grid dimensions.
                If None, uses bench_cfg.inputs_as_str(). Defaults to None.

        Returns:
            hv.GridSpace: A HoloViews GridSpace object showing the data as a grid.
        """
        if inputs is None:
            inputs = self.bench_cfg.inputs_as_str()
        if len(inputs) > 2:
            inputs = inputs[:2]
        return self.to_holomap().grid(inputs)


HoloviewResult.set_default_opts()
