from __future__ import annotations
from typing import Any, Literal
from collections.abc import Callable, Sequence
import logging
import panel as pn
from param import Parameter

from bencher.results.bench_result_base import EmptyContainer, ReduceType

try:
    from bencher.results.rerun_result import RerunResult
except ModuleNotFoundError:

    class RerunResult:  # pylint: disable=missing-class-docstring
        pass


from bencher.results.video_summary import VideoSummaryResult
from bencher.results.pane_result import PaneResult
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
from bencher.plugins.bench_data import BenchData, RunMeta
from bencher.plugins.registry import get_registry
from bencher.plugins.builtins import (
    CALLBACK_TO_PLUGIN,
    PANES_PLUGIN_NAME,
    register_builtin_plugins,
)
from bencher.utils import listify, resolve_aggregate


class BenchResult(
    # RerunResult resolves to either the real class or a fallback stub via the
    # try/except import above; ty sees that union and can't compute an MRO, but at
    # runtime exactly one definition is bound.
    RerunResult,  # ty: ignore[unsupported-base]
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
        new_instance.regression_report = original.regression_report
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
        result_instance.regression_report = self.regression_report
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
            PaneResult.to_panes,
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

    def to_bench_data(self, render_kwargs: dict | None = None) -> BenchData:
        """Snapshot this result as the frozen plugin data contract.

        The transitional ``legacy_result``/``render_kwargs`` fields carry the live
        result object and the plot kwargs for the wrapped built-in renderers; they
        disappear once renderers consume BenchData directly.

        Returns:
            BenchData: The frozen data handle plot plugins receive.
        """
        return BenchData(
            dataset=self.ds,
            input_vars=tuple(self.bench_cfg.input_vars),
            result_vars=tuple(self.bench_cfg.result_vars),
            plt_cnt_cfg=self.plt_cnt_cfg,
            run_meta=RunMeta(name=self.bench_cfg.bench_name or ""),
            legacy_result=self,
            render_kwargs=render_kwargs if render_kwargs is not None else {},
        )

    def to_auto(
        self,
        plot_list: list[callable | str] | None = None,
        remove_plots: list[callable | str] | None = None,
        default_container=pn.Column,
        override: bool = False,  # false so that plots that are not supported are not shown
        numeric_only: bool = False,
        backend: str | None = None,
        **kwargs,
    ) -> list[pn.panel]:
        """Automatically generate plots by dispatching through the plot plugin registry.

        Every registered plugin whose match rule fits this sweep renders, in
        priority order — the built-in chart types (registered in
        :mod:`bencher.plugins.builtins`) plus any user plugins registered with
        ``bencher.register_plugin`` / ``@bencher.plot_plugin`` or discovered via
        the ``bencher.plot_plugins`` entry-point group.

        Args:
            plot_list (list[callable | str], optional): Restrict to these plots. Entries are
                plugin names ("line", "heatmap", ...) or, for backward compatibility, legacy
                plot callbacks (e.g. ``LineResult.to_plot``); unrecognized callables are
                invoked directly as before. Defaults to None (all matching plugins).
            remove_plots (list[callable | str], optional): Plots to exclude, same entry
                forms as plot_list. Defaults to None.
            default_container (type, optional): Default container type for the plots. Defaults to pn.Column.
            override (bool, optional): Whether to override unsupported plots. Defaults to False.
            numeric_only (bool, optional): When True, skip the pane-type result plugin
                (images, videos, rerun, etc.) that cannot be numerically aggregated.
                Defaults to False.
            backend (str, optional): Preferred rendering backend. Chart types the
                preferred backend implements render through it; the rest keep their
                best other implementation. Defaults to None (highest priority wins).
            **kwargs: Additional keyword arguments for plot configuration.

        Returns:
            list[pn.panel]: A list of panel objects containing the generated plots.
        """
        self.plt_cnt_cfg.print_debug = False
        include_names, extra_callbacks = self._normalize_plot_list(listify(plot_list))
        exclude_names, extra_callbacks = self._plot_exclusions(
            listify(remove_plots), extra_callbacks, numeric_only
        )

        kwargs = self.set_plot_size(**kwargs)
        data = self.to_bench_data(render_kwargs=dict(override=override, **kwargs))

        row = EmptyContainer(default_container())
        for plugin in get_registry().select(
            data, include=include_names, exclude=exclude_names or None, backend=backend
        ):
            try:
                row.append(plugin.render(data))
            except Exception:  # pylint: disable=broad-except
                logging.error("Plot plugin %s failed", plugin.name, exc_info=True)
        for plot_callback in extra_callbacks:
            try:
                row.append(plot_callback(self, override=override, **kwargs))
            except Exception:  # pylint: disable=broad-except
                logging.error("Plot callback %s failed", plot_callback.__name__, exc_info=True)

        self.plt_cnt_cfg.print_debug = True
        if len(row.pane) == 0:
            row.append(pn.pane.Markdown("No Plotters are able to represent these results"))
        return row.pane

    @staticmethod
    def _normalize_plot_list(
        plot_list: list[callable | str] | None,
    ) -> tuple[list[str] | None, list[callable]]:
        """Split a to_auto plot_list into registry names and legacy callables.

        Known callbacks translate to their plugin names; unknown callables keep
        working through the legacy direct-call path. None means "no restriction"
        (all registered plugins participate)."""
        if plot_list is None:
            return None, []
        include_names: list[str] = []
        extra_callbacks: list[callable] = []
        for entry in plot_list:
            if isinstance(entry, str):
                include_names.append(entry)
            elif entry in CALLBACK_TO_PLUGIN:
                include_names.append(CALLBACK_TO_PLUGIN[entry])
            else:
                extra_callbacks.append(entry)
        return include_names, extra_callbacks

    @staticmethod
    def _plot_exclusions(
        remove_plots: list[callable | str] | None,
        extra_callbacks: list[callable],
        numeric_only: bool,
    ) -> tuple[set[str], list[callable]]:
        """Compute the plugin names to exclude and drop removed legacy callables."""
        exclude_names: set[str] = set()
        if numeric_only:
            exclude_names.add(PANES_PLUGIN_NAME)
        kept_callbacks = list(extra_callbacks)
        if remove_plots is not None:
            for entry in remove_plots:
                if isinstance(entry, str):
                    exclude_names.add(entry)
                elif entry in CALLBACK_TO_PLUGIN:
                    exclude_names.add(CALLBACK_TO_PLUGIN[entry])
                elif entry in kept_callbacks:
                    kept_callbacks.remove(entry)
        return exclude_names, kept_callbacks

    def to_auto_plots(
        self,
        extra_panels: Sequence[Callable[[BenchResult], pn.viewable.Viewable] | pn.viewable.Viewable]
        | None = None,
        **kwargs,
    ) -> pn.panel:
        """Given the dataset result of a benchmark run, automatically deduce how to plot the data based on the types of variables that were sampled.

        Args:
            extra_panels: Extra panel callables or static panels to inject after the sweep
                summary and before aggregate/auto plots. Each item is either a
                callable(BenchResult) -> panel, or a static panel object.
            **kwargs: Additional keyword arguments for plot configuration.

        Returns:
            pn.panel: A panel containing plot results.
        """
        plot_cols = pn.Column()
        plot_cols.append(self.to_sweep_summary(name="Plots View"))

        # --- Regression report (auto-inserted when regression detection is enabled) ---
        # Summary table surfaces whenever a regression fires (including the
        # absolute-method case which has no history and therefore no overlay).
        has_multiple_times = "over_time" in self.ds.dims and self.ds.sizes["over_time"] > 1
        if self.regression_report is not None and self.regression_report.has_regressions:
            plot_cols.append(
                pn.pane.Markdown(
                    self.regression_report.to_markdown(),
                    name="Regression Report",
                    width=800,
                )
            )
        if self.regression_report is not None and has_multiple_times:
            for r in self.regression_report.results:
                if r.historical is None or len(r.historical) == 0:
                    continue
                try:
                    plot_cols.append(pn.pane.HoloViews(r.render_overlay()))
                except Exception:  # pylint: disable=broad-except
                    logging.error(
                        "Failed to render regression overlay for %s", r.variable, exc_info=True
                    )

        # --- Extra panels (user-injected) ---
        if extra_panels:
            for ep in extra_panels:
                try:
                    if callable(ep):
                        plot_cols.append(ep(self))
                    else:
                        plot_cols.append(ep)
                except Exception:  # pylint: disable=broad-except
                    name = getattr(ep, "__name__", repr(ep))
                    logging.error("Extra panel %s failed", name, exc_info=True)

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
                        numeric_only=True,
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
            deep=False,
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


# The built-in chart set dispatches through the plugin registry (see to_auto);
# register it as soon as the result classes exist so any import path that can
# construct a BenchResult also has the registry populated.
register_builtin_plugins()
