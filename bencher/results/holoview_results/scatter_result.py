from __future__ import annotations
from typing import Optional
import panel as pn

import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
from bencher.results.bench_result_base import ReduceType

from bencher.plotting.plot_filter import VarRange, PlotFilter


from bencher.results.holoview_results.holoview_result import HoloviewResult


class ScatterResult(HoloviewResult):
    """A class for creating scatter plots from benchmark results.

    Scatter plots are useful for visualizing the distribution of individual data points
    and identifying patterns, clusters, or outliers. This class provides methods to
    generate scatter plots with jittering capabilities to better visualize overlapping
    points, particularly useful for displaying benchmark results across multiple repetitions.

    Methods include:
    - to_scatter_jitter: Creates scatter plots with jittering for better visualization of overlapping points
    - to_scatter: Creates standard scatter plots that can be grouped by categorical variables
    """

    def to_plot(self, override: bool = True, **kwargs) -> Optional[pn.panel]:
        """Creates a standard scatter plot from benchmark data.

        This is a convenience method that calls to_scatter() with the same parameters.

        Args:
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the scatter plot options.

        Returns:
            Optional[pn.panel]: A panel containing the scatter plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.to_scatter(override=override, **kwargs)

    def to_scatter(self, override: bool = True, **kwargs) -> Optional[pn.panel]:
        """Creates a standard scatter plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a scatter plot
        and generates a visualization with points representing individual data points.
        When categorical variables are present, the scatter points can be grouped.

        Args:
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the scatter plot options.

        Returns:
            Optional[pn.panel]: A panel containing the scatter plot if data is appropriate,
                              otherwise returns filter match results.
        """
        match_res = PlotFilter(
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
        ).matches_result(self.plt_cnt_cfg, "to_hvplot_scatter", override=override)
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

    # def to_scatter_jitter(
    #     self, result_var: Parameter = None, override: bool = True, **kwargs
    # ) -> Optional[pn.panel]:
    #     return self.filter(
    #         self.to_scatter_ds,
    #         float_range=VarRange(0, 0),
    #         cat_range=VarRange(0, None),
    #         repeats_range=VarRange(2, None),
    #         reduce=ReduceType.NONE,
    #         target_dimension=2,
    #         result_var=result_var,
    #         result_types=(ResultVar),
    #         override=override,
    #         **kwargs,
    #     )

    # def to_scatter_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs) -> hv.Scatter:
    #     by = None
    #     if self.plt_cnt_cfg.cat_cnt >= 2:
    #         by = self.plt_cnt_cfg.cat_vars[1].name
    #     # print(dataset)
    #     da_plot = dataset[result_var.name]
    #     # da_plot = dataset
    #     # print(da_plot)
    #     print("by", by)
    #     title = self.title_from_ds(da_plot, result_var, **kwargs)
    #     time_widget_args = self.time_widget(title)
    #     print(da_plot)
    #     # return da_plot.hvplot.box(by=by, **time_widget_args, **kwargs)
    #     # return da_plot.hvplot.box( **time_widget_args, **kwargs)
    #     return da_plot.hvplot.scatter(
    #         y=result_var.name, x="repeat", by=by, **time_widget_args, **kwargs
    #     ).opts(jitter=0.1)
