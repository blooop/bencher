from __future__ import annotations
import logging
from typing import List, Optional
import panel as pn
import holoviews as hv
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.utils import (
    hmap_canonical_input,
    get_nearest_coords,
    get_nearest_coords1D,
    listify,
)
from bencher.results.panel_result import PanelResult
from bencher.results.bench_result_base import ReduceType

from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.variables.results import ResultVar, ResultImage, ResultVideo

hv.extension("bokeh", "plotly")

# Flag to enable or disable tap tool functionality in visualizations
use_tap = True


class HoloviewResult(PanelResult):
    @staticmethod
    def set_default_opts(width=600, height=600):
        width_heigh = {"width": width, "height": height, "tools": ["hover"]}
        hv.opts.defaults(
            hv.opts.Curve(**width_heigh),
            hv.opts.Points(**width_heigh),
            hv.opts.Bars(**width_heigh),
            hv.opts.Scatter(**width_heigh),
            hv.opts.HeatMap(cmap="plasma", **width_heigh, colorbar=True),
            # hv.opts.Surface(**width_heigh),
            hv.opts.GridSpace(plot_size=400),
        )
        return width_heigh

    def to(self, hv_type: hv.Chart, reduce: ReduceType = ReduceType.AUTO, **kwargs) -> hv.Chart:
        return self.to_hv_dataset(reduce).to(hv_type, **kwargs)

    def overlay_plots(self, plot_callback: callable) -> Optional[hv.Overlay]:
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

    def layout_plots(self, plot_callback: callable):
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

    def time_widget(self, title):
        return {"title": title}
        # if self.bench_cfg.over_time:
        #     time_widget_args = {"widget_type": "scrubber", "widget_location": "bottom"}
        #     time_widget_args["title"] = None  # use the title generated by the widget instead
        # else:
        #     time_widget_args = {"widget_type": "individual"}
        #     time_widget_args["title"] = title

        # return time_widget_args

    def to_bar(
        self, result_var: Parameter = None, override: bool = False, **kwargs
    ) -> Optional[pn.panel]:
        return self.filter(
            self.to_bar_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            panel_range=VarRange(0, None),
            reduce=ReduceType.SQUEEZE,
            target_dimension=2,
            result_var=result_var,
            result_types=(ResultVar),
            override=override,
            **kwargs,
        )

    def to_bar_ds(self, dataset: xr.Dataset, result_var: Parameter = None, **kwargs):
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 2:
            by = self.plt_cnt_cfg.cat_vars[1].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        time_widget_args = self.time_widget(title)
        return da_plot.hvplot.bar(by=by, **time_widget_args, **kwargs)

    def hv_container_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        container: hv.Chart = None,
        **kwargs,
    ):
        return hv.Dataset(dataset[result_var.name]).to(container).opts(**kwargs)

    def to_hv_container(
        self,
        container: pn.pane.panel,
        reduce_type=ReduceType.AUTO,
        target_dimension: int = 2,
        result_var: Parameter = None,
        result_types=(ResultVar),
        **kwargs,
    ) -> Optional[pn.pane.panel]:
        return self.map_plot_panes(
            partial(self.hv_container_ds, container=container),
            hv_dataset=self.to_hv_dataset(reduce_type),
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=result_types,
            **kwargs,
        )

    def to_line(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        target_dimension=2,
        **kwargs,
    ) -> Optional[pn.panel]:
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
            **kwargs,
        )

    def to_line_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        x = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        time_widget_args = self.time_widget(title)
        return da_plot.hvplot.line(x=x, by=by, **time_widget_args, **kwargs)

    def to_curve(self, result_var: Parameter = None, **kwargs):
        return self.filter(
            self.to_curve_ds,
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.REDUCE,
            # reduce=ReduceType.MINMAX,
            target_dimension=2,
            result_var=result_var,
            result_types=(ResultVar),
            **kwargs,
        )

    def to_curve_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> Optional[hv.Curve]:
        hvds = hv.Dataset(dataset)
        title = self.title_from_ds(dataset, result_var, **kwargs)
        # print(result_var.name)
        # print( dataset)
        pt = hv.Overlay()
        # find pairs of {var_name} {var_name}_std to plot the line and their spreads.
        var = result_var.name
        std_var = f"{var}_std"

        pt *= hvds.to(hv.Curve, vdims=var, label=var).opts(title=title, **kwargs)
        # Only create a Spread if the matching _std variable exists
        if std_var in dataset.data_vars:
            pt *= hvds.to(hv.Spread, vdims=[var, std_var])

        # for var in dataset.data_vars:
        #     print(var)
        #     if not var.endswith("_std"):
        #         std_var = f"{var}_std"
        #         pt *= hvds.to(hv.Curve, vdims=var, label=var).opts(title=title, **kwargs)
        #         #Only create a Spread if the matching _std variable exists
        #         if std_var in dataset.data_vars:
        #             pt *= hvds.to(hv.Spread, vdims=[var, std_var])

        return pt.opts(legend_position="right")

    def to_heatmap(
        self,
        result_var: Parameter = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row = None,
        target_dimension=2,
        **kwargs,
    ) -> Optional[pn.panel]:
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
            **kwargs,
        )

    def to_heatmap_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> Optional[hv.HeatMap]:
        if len(dataset.dims) >= 2:
            x = self.bench_cfg.input_vars[0].name
            y = self.bench_cfg.input_vars[1].name
            C = result_var.name
            title = f"Heatmap of {result_var.name}"
            time_args = self.time_widget(title)
            return dataset.hvplot.heatmap(x=x, y=y, C=C, cmap="plasma", **time_args, **kwargs)
        return None

    def result_var_to_container(self, result_var):
        if isinstance(result_var, ResultImage):
            return pn.pane.PNG
        return pn.pane.Video if isinstance(result_var, ResultVideo) else pn.Column

    def setup_results_and_containers(self, result_var_plots, container, **kwargs):
        result_var_plots = listify(result_var_plots)
        if container is None:
            containers = [self.result_var_to_container(rv) for rv in result_var_plots]
        else:
            containers = listify(container)

        cont_instances = [c(**kwargs) if c is not None else None for c in containers]
        return result_var_plots, cont_instances

    def to_heatmap_container_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: List[Parameter] = None,
        container: pn.pane.panel = None,
        tap_container_direction: pn.Column | pn.Row = None,
        **kwargs,
    ) -> pn.Row:
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

    def to_line_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: List[Parameter] = None,
        container: pn.pane.panel = pn.pane.panel,
        **kwargs,
    ) -> pn.Row:
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

    def to_error_bar(self) -> hv.Bars:
        return self.to_hv_dataset(ReduceType.REDUCE).to(hv.ErrorBars)

    def to_points(self, reduce: ReduceType = ReduceType.AUTO) -> hv.Points:
        ds = self.to_hv_dataset(reduce)
        pt = ds.to(hv.Points)
        if reduce:
            pt *= ds.to(hv.ErrorBars)
        return pt

    def to_scatter(self, **kwargs) -> Optional[pn.panel]:
        match_res = PlotFilter(
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_hvplot_scatter")
        if match_res.overall:
            hv_ds = self.to_hv_dataset(ReduceType.SQUEEZE)
            by = None
            subplots = False
            if self.plt_cnt_cfg.cat_cnt > 1:
                by = [v.name for v in self.bench_cfg.input_vars[1:]]
                subplots = False
            return hv_ds.data.hvplot.scatter(by=by, subplots=subplots, **kwargs).opts(
                title=self.to_plot_title()
            )
        return match_res.to_panel(**kwargs)

    # def to_scatter_jitter(self, **kwargs) -> Optional[hv.Scatter]:
    #     matches = PlotFilter(
    #         float_range=VarRange(0, 0),
    #         cat_range=VarRange(0, None),
    #         repeats_range=VarRange(2, None),
    #         input_range=VarRange(1, None),
    #     ).matches_result(self.plt_cnt_cfg, "to_scatter_jitter")
    #     if matches.overall:
    #         hv_ds = self.to_hv_dataset(ReduceType.NONE)

    #         by = None
    #         groupby = None
    #         subplots=False
    #         if self.plt_cnt_cfg.cat_cnt > 1:
    #             by = [v.name for v in self.bench_cfg.all_vars[1:]]
    #             subplots=False
    #         return hv_ds.data.hvplot.scatter(by=by,subplots=subplots, **kwargs).opts(title=self.to_plot_title())

    #         # pt = (
    #         #     hv_ds.to(hv.Scatter)
    #         #     .opts(jitter=0.1)
    #         #     .overlay("repeat")
    #         #     .opts(show_legend=False, title=self.to_plot_title(), **kwargs)
    #         # )
    #         # return pt
    #     return matches.to_panel()

    # def to_scatter_jitter_multi(self, **kwargs) -> Optional[hv.Scatter]:
    #     matches = PlotFilter(
    #         float_range=VarRange(0, 0),
    #         cat_range=VarRange(0, None),
    #         repeats_range=VarRange(2, None),
    #         input_range=VarRange(1, None),
    #     ).matches_result(self.plt_cnt_cfg, "to_scatter_jitter")
    #     if matches.overall:
    #         hv_dataset = self.to_hv_dataset(ReduceType.NONE)

    #         print("KDIMS",hv_dataset.kdims)
    #         # hv_dataset.kdims =[hv_dataset.kdims[2],hv_dataset.kdims[1],hv_dataset.kdims[0]]
    #         # print("KDIMS",hv_dataset.kdims)

    #         # exit()
    #         cb = partial(self.to_scatter_jitter_da, **kwargs)
    #         return self.to_panes_multi_panel(hv_dataset, None, plot_callback=cb, target_dimension=3)
    #     return matches.to_panel()

    # def to_scatter_jitter_da(self, ds: xr.Dataset, **kwargs) -> Optional[hv.Scatter]:
    #     matches = PlotFilter(
    #         float_range=VarRange(0, 0),
    #         cat_range=VarRange(0, None),
    #         repeats_range=VarRange(2, None),
    #         input_range=VarRange(1, None),
    #     ).matches_result(self.plt_cnt_cfg, "to_scatter_jitter")
    #     if matches.overall:

    #         print("DA IN",da)
    #         da = self.to_hv_dataset(ReduceType.NONE)
    #         hvds = hv.Dataset(da)
    #         # return None

    #         # print("DA FRESH",da)
    #         result_var = self.bench_cfg.result_vars[0]

    #         print(hvds.data.sizes)
    #         print("repeat" in hvds.data.sizes)
    #         # if "repeat" in hvds.data.sizes:
    #         # try:
    #         #     pt = (
    #         #         hvds.to(hv.Scatter)
    #         #         .opts(jitter=0.1)
    #         #         # .overlay()
    #         #         .overlay("repeat")
    #         #         .opts(show_legend=False, title=self.to_plot_title(), clabel=result_var.name, **kwargs)
    #         #     )
    #         # except:
    #         pt = (
    #             hvds.to(hv.Scatter)
    #             .opts(jitter=0.1)
    #             # .overlay()
    #             # .overlay("repeat")
    #             .opts(show_legend=False, title=self.to_plot_title(), clabel=result_var.name, **kwargs)
    #         )
    #         return pt
    #     return matches.to_panel()

    def to_scatter_jitter(
        self,
        result_var: Parameter = None,
        override: bool = False,
        **kwargs,  # pylint: disable=unused-argument
    ) -> List[hv.Scatter]:
        return self.overlay_plots(
            partial(self.to_scatter_jitter_single, override=override, **kwargs)
        )

    def to_scatter_jitter_single(
        self, result_var: Parameter, override: bool = True, **kwargs
    ) -> Optional[hv.Scatter]:
        matches = PlotFilter(
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            input_range=VarRange(1, None),
        ).matches_result(self.plt_cnt_cfg, "to_scatter_jitter", override)
        if matches.overall:
            ds = self.to_hv_dataset(ReduceType.NONE)
            pt = (
                ds.to(hv.Scatter, vdims=[result_var.name], label=result_var.name)
                .opts(jitter=0.1, show_legend=False, title=self.to_plot_title(), **kwargs)
                .overlay("repeat")
            )
            return pt
        return matches.to_panel()

    def to_heatmap_single(
        self, result_var: Parameter, reduce: ReduceType = ReduceType.AUTO, **kwargs
    ) -> hv.HeatMap:
        matches_res = PlotFilter(
            float_range=VarRange(2, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(1, None),
        ).matches_result(self.plt_cnt_cfg, "to_heatmap")
        if matches_res.overall:
            z = result_var
            title = f"{z.name} vs ("

            for iv in self.bench_cfg.input_vars:
                title += f" vs {iv.name}"
            title += ")"

            color_label = f"{z.name} [{z.units}]"

            return self.to(hv.HeatMap, reduce).opts(clabel=color_label, **kwargs)
        return matches_res.to_panel()

    def to_heatmap_tap(
        self,
        result_var: Parameter,
        reduce: ReduceType = ReduceType.AUTO,
        width=800,
        height=800,
        **kwargs,
    ):
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

    def to_nd_layout(self, hmap_name: str) -> hv.NdLayout:
        return hv.NdLayout(self.get_hmap(hmap_name), kdims=self.bench_cfg.hmap_kdims).opts(
            shared_axes=False, shared_datasource=False
        )

    def to_holomap(self, name: str = None) -> hv.HoloMap:
        return hv.HoloMap(self.to_nd_layout(name)).opts(shared_axes=False)

    def to_holomap_list(self, hmap_names: List[str] = None) -> hv.HoloMap:
        if hmap_names is None:
            hmap_names = [i.name for i in self.result_hmaps]
        col = pn.Column()
        for name in hmap_names:
            self.to_holomap(name)
        return col

    def get_nearest_holomap(self, name: str = None, **kwargs):
        canonical_inp = hmap_canonical_input(
            get_nearest_coords(self.ds, collapse_list=True, **kwargs)
        )
        return self.get_hmap(name)[canonical_inp].opts(framewise=True)

    def to_dynamic_map(self, name: str = None) -> hv.DynamicMap:
        """use the values stored in the holomap dictionary to populate a dynamic map. Note that this is much faster than passing the holomap to a holomap object as the values are calculated on the fly"""

        def cb(**kwargs):
            return self.get_hmap(name)[hmap_canonical_input(kwargs)].opts(
                framewise=True, shared_axes=False
            )

        kdims = []
        for i in self.bench_cfg.input_vars + [self.bench_cfg.iv_repeat]:
            kdims.append(i.as_dim(compute_values=True))

        return hv.DynamicMap(cb, kdims=kdims)

    def to_grid(self, inputs=None):
        if inputs is None:
            inputs = self.bench_cfg.inputs_as_str()
        if len(inputs) > 2:
            inputs = inputs[:2]
        return self.to_holomap().grid(inputs)

    def to_table(self):
        return self.to(hv.Table, ReduceType.SQUEEZE)

    def to_tabulator(self, **kwargs):
        """Passes the data to the panel Tabulator type to display an interactive table
        see https://panel.holoviz.org/reference/widgets/Tabulator.html for extra options
        """
        return pn.widgets.Tabulator(self.to_pandas(), **kwargs)

    def to_surface(self, result_var: Parameter = None, **kwargs) -> Optional[pn.pane.Pane]:
        return self.filter(
            self.to_surface_ds,
            float_range=VarRange(2, None),
            cat_range=VarRange(0, None),
            input_range=VarRange(1, None),
            reduce=ReduceType.REDUCE,
            target_dimension=2,
            result_var=result_var,
            result_types=(ResultVar),
            **kwargs,
        )

    def to_surface_ds(
        self, dataset: xr.Dataset, result_var: Parameter, alpha: float = 0.3, **kwargs
    ) -> Optional[pn.panel]:
        """Given a benchCfg generate a 2D surface plot

        Args:
            result_var (Parameter): result variable to plot

        Returns:
            pn.pane.holoview: A 2d surface plot as a holoview in a pane
        """
        matches_res = PlotFilter(
            float_range=VarRange(2, 2),
            cat_range=VarRange(0, None),
            vector_len=VarRange(1, 1),
            result_vars=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_surface_hv")
        if matches_res.overall:
            # xr_cfg = plot_float_cnt_2(self.plt_cnt_cfg, result_var)

            # TODO a warning suggests setting this parameter, but it does not seem to help as expected, leaving here to fix in the future
            # hv.config.image_rtol = 1.0

            mean = dataset[result_var.name]

            hvds = hv.Dataset(dataset[result_var.name])

            x = self.plt_cnt_cfg.float_vars[0]
            y = self.plt_cnt_cfg.float_vars[1]

            try:
                surface = hvds.to(hv.Surface, vdims=[result_var.name])
                surface = surface.opts(colorbar=True)
            except Exception as e:  # pylint: disable=broad-except
                logging.warning(e)

            if self.bench_cfg.repeats > 1:
                std_dev = dataset[f"{result_var.name}_std"]

                upper = mean + std_dev
                upper.name = result_var.name

                lower = mean - std_dev
                lower.name = result_var.name

                surface *= (
                    hv.Dataset(upper)
                    .to(hv.Surface)
                    .opts(alpha=alpha, colorbar=False, backend="plotly")
                )
                surface *= (
                    hv.Dataset(lower)
                    .to(hv.Surface)
                    .opts(alpha=alpha, colorbar=False, backend="plotly")
                )

            surface = surface.opts(
                zlabel=f"{result_var.name} [{result_var.units}]",
                title=f"{result_var.name} vs ({x.name} and {y.name})",
                backend="plotly",
                **kwargs,
            )

            if self.bench_cfg.render_plotly:
                hv.extension("plotly")
                out = surface
            else:
                # using render disabled the holoviews sliders :(
                out = hv.render(surface, backend="plotly")
            return pn.Column(out, name="surface_hv")

        return matches_res.to_panel()

    # def plot_scatter2D_hv(self, rv: ParametrizedSweep) -> pn.pane.Plotly:
    # import plotly.express as px

    #     """Given a benchCfg generate a 2D scatter plot

    #     Args:
    #         bench_cfg (BenchCfg): description of benchmark
    #         rv (ParametrizedSweep): result variable to plot

    #     Returns:
    #         pn.pane.Plotly: A 3d volume plot as a holoview in a pane
    #     """

    #     # bench_cfg = wrap_long_time_labels(bench_cfg)
    #     self.ds.drop_vars("repeat")

    #     df = self.to_pandas()

    #     names = rv.index_names()

    #     return px.scatter(
    #         df, x=names[0], y=names[1], marginal_x="histogram", marginal_y="histogram"
    #     )


HoloviewResult.set_default_opts()
