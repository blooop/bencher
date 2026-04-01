from __future__ import annotations
from typing import Any, Literal
import logging
import panel as pn
from param import Parameter

from bencher.results.bench_result_base import EmptyContainer, ReduceType
from bencher.results.video_summary import VideoSummaryResult
from bencher.results.video_result import VideoResult
from bencher.results.volume_result import VolumeResult
from bencher.results.holoview_results.holoview_result import HoloviewResult

# Updated imports for distribution result classes
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.curve_result import CurveResult
from bencher.results.holoview_results.band_result import BandResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.histogram_result import HistogramResult
from bencher.results.optuna_result import OptunaResult
from bencher.results.dataset_result import DataSetResult
from bencher.utils import listify, resolve_aggregate


class BenchResult(
    VolumeResult,
    BoxWhiskerResult,
    ViolinResult,
    ScatterJitterResult,
    ScatterResult,
    LineResult,
    BarResult,
    HeatmapResult,
    CurveResult,
    BandResult,
    SurfaceResult,
    HistogramResult,
    HoloviewResult,
    VideoSummaryResult,
    DataSetResult,
    OptunaResult,
):  # noqa pylint: disable=too-many-ancestors
    """Contains the results of the benchmark and has methods to cast the results to various datatypes and graphical representations"""

    def __init__(self, bench_cfg) -> None:
        """Initialize a BenchResult instance.

        Args:
            bench_cfg: The benchmark configuration object containing settings and result data
        """
        VolumeResult.__init__(self, bench_cfg)
        HoloviewResult.__init__(self, bench_cfg)
        # DataSetResult.__init__(self.bench_cfg)
        self.timings = None  # Populated by Bench.run_sweep() with SweepTimings

    @classmethod
    def from_existing(cls, original: BenchResult) -> BenchResult:
        new_instance = cls(original.bench_cfg)
        new_instance.ds = original.ds
        new_instance.bench_cfg = original.bench_cfg
        new_instance.plt_cnt_cfg = original.plt_cnt_cfg
        return new_instance

    def to(
        self,
        result_type: BenchResult,
        result_var: Parameter | None = None,
        override: bool = True,
        reduce: ReduceType | None = None,
        # Aggregation controls (applied in filter())
        aggregate: bool | int | list[str] | None = None,
        agg_fn: Literal["mean", "sum", "max", "min", "median"] = "mean",
        **kwargs: Any,
    ) -> BenchResult:
        """Return the current instance of BenchResult.

        Returns:
            BenchResult: The current instance of the benchmark result
        """
        input_var_names = [iv.name for iv in self.bench_cfg.input_vars]
        agg_over_dims = resolve_aggregate(aggregate, input_var_names)

        result_instance = result_type(self.bench_cfg)
        result_instance.ds = self.ds
        result_instance.plt_cnt_cfg = self.plt_cnt_cfg
        result_instance.dataset_list = self.dataset_list
        # Build kwargs for the plot call, only include reduce if explicitly set
        plot_kwargs = dict(
            result_var=result_var,
            override=override,
            agg_over_dims=agg_over_dims,
            agg_fn=agg_fn,
        )
        if reduce is not None:
            plot_kwargs["reduce"] = reduce
        plot_kwargs.update(kwargs)
        return result_instance.to_plot(**plot_kwargs)

    @staticmethod
    def default_plot_callbacks() -> list[callable]:
        """Get the default list of plot callback functions.

        These callbacks are used by default in the to_auto method if no specific
        plot list is provided.

        Returns:
            list[callable]: A list of plotting callback functions
        """
        return [
            # VideoSummaryResult.to_video_summary, #quite expensive so not turned on by default
            BarResult.to_plot,
            BoxWhiskerResult.to_plot,
            # ViolinResult.to_violin,
            # ScatterJitterResult.to_plot,
            CurveResult.to_plot,
            LineResult.to_plot,
            HeatmapResult.to_plot,
            HistogramResult.to_plot,
            VolumeResult.to_plot,
            # PanelResult.to_video,
            VideoResult.to_panes,
        ]

    @staticmethod
    def plotly_callbacks() -> list[callable]:
        """Get the list of Plotly-specific callback functions.

        Returns:
            list[callable]: A list of Plotly-based visualization callback functions
        """
        return [SurfaceResult.to_surface, VolumeResult.to_volume]

    def plot(self) -> pn.panel:
        """Plots the benchresult using the plot callbacks defined by the bench run.

        This method uses the plot_callbacks defined in the bench_cfg to generate
        plots for the benchmark results.

        Returns:
             pn.panel: A panel representation of the results, or None if no plot_callbacks defined
        """
        if self.bench_cfg.plot_callbacks is not None:
            return pn.Column(*[cb(self) for cb in self.bench_cfg.plot_callbacks])
        return None

    def to_auto(
        self,
        plot_list: list[callable] | None = None,
        remove_plots: list[callable] | None = None,
        default_container=pn.Column,
        override: bool = False,  # false so that plots that are not supported are not shown
        **kwargs,
    ) -> list[pn.panel]:
        """Automatically generate plots based on the provided plot callbacks.

        Args:
            plot_list (list[callable], optional): List of plot callback functions to use. Defaults to None.
            remove_plots (list[callable], optional): List of plot callback functions to exclude. Defaults to None.
            default_container (type, optional): Default container type for the plots. Defaults to pn.Column.
            override (bool, optional): Whether to override unsupported plots. Defaults to False.
            **kwargs: Additional keyword arguments for plot configuration.

        Returns:
            list[pn.panel]: A list of panel objects containing the generated plots.
        """
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
            # the callbacks are passed from the static class definition, so self needs to be
            # passed before the plotting callback can be called
            try:
                row.append(plot_callback(self, override=override, **kwargs))
            except Exception:  # pylint: disable=broad-except
                logging.error("Plot callback %s failed", plot_callback.__name__, exc_info=True)

        self.plt_cnt_cfg.print_debug = True
        if len(row.pane) == 0:
            row.append(pn.pane.Markdown("No Plotters are able to represent these results"))
        return row.pane

    def to_auto_plots(self, **kwargs) -> pn.panel:
        """Given the dataset result of a benchmark run, automatically deduce how to plot the data based on the types of variables that were sampled.

        Args:
            **kwargs: Additional keyword arguments for plot configuration.

        Returns:
            pn.panel: A panel containing plot results.
        """
        plot_cols = pn.Column()
        plot_cols.append(self.to_sweep_summary(name="Plots View"))

        # --- Dimension aggregation (orthogonal to over_time) ---
        if self.bench_cfg.agg_over_dims and self.bench_cfg.show_aggregate_plots:
            dims = ", ".join(self.bench_cfg.agg_over_dims)
            all_input_names = {iv.name for iv in self.bench_cfg.input_vars}
            agg_set = set(self.bench_cfg.agg_over_dims)
            fully_aggregated = all_input_names <= agg_set
            if fully_aggregated and not self.bench_cfg.over_time:
                # All input dims collapsed, no over_time: scalar summary table.
                plot_cols.append(
                    pn.pane.Markdown(f"### Aggregated View\nAggregated over: **{dims}**")
                )
                plot_cols.append(self._scalar_aggregate_summary())
            else:
                # Partial aggregation (or full with over_time): let to_auto pick
                # the right plotter for the remaining dims.
                plot_cols.append(
                    pn.pane.Markdown(f"### Aggregated View\nAggregated over: **{dims}**")
                )
                agg_kwargs = {
                    k: v for k, v in kwargs.items() if k not in ("agg_over_dims", "agg_fn")
                }
                plot_cols.append(
                    self.to_auto(
                        agg_over_dims=self.bench_cfg.agg_over_dims,
                        agg_fn=self.bench_cfg.agg_fn,
                        **agg_kwargs,
                    )
                )

        # --- Over-time band plot (orthogonal to dimension aggregation) ---
        if (
            self.bench_cfg.over_time
            and "over_time" in self.ds.dims
            and self.ds.sizes["over_time"] > 1
            and self.bench_cfg.input_vars
        ):
            input_names = [iv.name for iv in self.bench_cfg.input_vars]
            plot_cols.append(
                pn.pane.Markdown(
                    "### Over Time\nPercentile bands across all input dimensions over time"
                )
            )
            plot_cols.append(self.to(BandResult, aggregate=input_names))

        kwargs.setdefault("pane_layout", self.bench_cfg.pane_layout)
        plot_cols.append(self.to_auto(**kwargs))
        plot_cols.append(self.bench_cfg.to_post_description())
        return plot_cols

    def _scalar_aggregate_summary(self) -> pn.pane.Markdown:
        """Render a Markdown table for a fully-aggregated (scalar) result."""
        ds = self.to_dataset(
            reduce=ReduceType.REDUCE,
            agg_over_dims=self.bench_cfg.agg_over_dims,
            agg_fn=self.bench_cfg.agg_fn,
        )
        rows = []
        for rv in self.bench_cfg.result_vars:
            name = rv.name
            if name not in ds.data_vars:
                continue
            val = float(ds[name].values)
            std_name = f"{name}_std"
            units = getattr(rv, "units", "")
            if std_name in ds.data_vars:
                std = float(ds[std_name].values)
                rows.append(f"| {name} | {val:.4g} ± {std:.4g} | {units} |")
            else:
                rows.append(f"| {name} | {val:.4g} | {units} |")
        header = "| Result | Value | Units |\n|---|---|---|"
        return pn.pane.Markdown(
            f"{header}\n" + "\n".join(rows) if rows else "No result variables found."
        )
