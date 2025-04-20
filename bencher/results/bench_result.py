from __future__ import annotations
from typing import List
import panel as pn

from bencher.results.bench_result_base import EmptyContainer
from bencher.results.video_summary import VideoSummaryResult
from bencher.results.panel_result import PanelResult
from bencher.results.plotly_result import PlotlyResult
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.holoview_results.box_whisker_result import BoxWhiskerResult
from bencher.results.holoview_results.violin_result import ViolinResult
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.curve_result import CurveResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.hvplot_result import HvplotResult
from bencher.results.dataset_result import DataSetResult
from bencher.utils import listify


class BenchResult(
    PlotlyResult,
    BoxWhiskerResult,
    ViolinResult,
    ScatterResult,
    LineResult,
    BarResult,
    HeatmapResult,
    CurveResult,
    SurfaceResult,
    HoloviewResult,
    HvplotResult,
    VideoSummaryResult,
    DataSetResult,
):  # noqa pylint: disable=too-many-ancestors
    """Contains the results of the benchmark and has methods to cast the results to various datatypes and graphical representations"""

    def __init__(self, bench_cfg) -> None:
        PlotlyResult.__init__(self, bench_cfg)
        HoloviewResult.__init__(self, bench_cfg)
        # DataSetResult.__init__(self.bench_cfg)

    @staticmethod
    def default_plot_callbacks():
        return [
            # VideoSummaryResult.to_video_summary, #quite expensive so not turned on by default
            BarResult.to_bar,
            BoxWhiskerResult.to_boxplot,
            # ViolinResult.to_violin,
            # ScatterResult.to_scatter_jitter,  # needs to be fixed
            CurveResult.to_curve,
            LineResult.to_line,
            HeatmapResult.to_heatmap,
            HvplotResult.to_histogram,
            PlotlyResult.to_volume,
            # PanelResult.to_video,
            PanelResult.to_panes,
        ]

    @staticmethod
    def plotly_callbacks():
        return [SurfaceResult.to_surface, PlotlyResult.to_volume]

    def plot(self) -> pn.panel:
        """Plots the benchresult using the plot callbacks defined by the bench run

        Returns:
             pn.panel: A panel representation of the results
        """
        if self.bench_cfg.plot_callbacks is not None:
            return pn.Column(*[cb(self) for cb in self.bench_cfg.plot_callbacks])
        return None

    def to_auto(
        self,
        plot_list: List[callable] = None,
        remove_plots: List[callable] = None,
        default_container=pn.Column,
        override: bool = False,  # false so that plots that are not supported are not shown
        **kwargs,
    ) -> List[pn.panel]:
        self.plt_cnt_cfg.print_debug = False
        plot_list = listify(plot_list)
        remove_plots = listify(remove_plots)

        if plot_list is None:
            plot_list = BenchResult.default_plot_callbacks()
        if remove_plots is not None:
            for p in remove_plots:
                plot_list.remove(p)

        kwargs = self.set_plot_size(**kwargs)

        row = EmptyContainer(default_container())
        for plot_callback in plot_list:
            if self.plt_cnt_cfg.print_debug:
                print(f"checking: {plot_callback.__name__}")
            # the callbacks are passed from the static class definition, so self needs to be passed before the plotting callback can be called
            row.append(plot_callback(self, override=override, **kwargs))

        self.plt_cnt_cfg.print_debug = True
        if len(row.pane) == 0:
            row.append(
                pn.pane.Markdown("No Plotters are able to represent these results", **kwargs)
            )
        return row.pane

    def to_auto_plots(self, **kwargs) -> pn.panel:
        """Given the dataset result of a benchmark run, automatically dedeuce how to plot the data based on the types of variables that were sampled

        Args:
            bench_cfg (BenchCfg): Information on how the benchmark was sampled and the resulting data

        Returns:
            pn.pane: A panel containing plot results
        """

        plot_cols = pn.Column()
        plot_cols.append(self.to_sweep_summary(name="Plots View"))
        plot_cols.append(self.to_auto(**kwargs))
        plot_cols.append(self.bench_cfg.to_post_description())
        return plot_cols
