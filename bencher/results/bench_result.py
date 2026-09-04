from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import panel as pn
from param import Parameter

from bencher.results.bench_result_base import EmptyContainer, ReduceType
from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    PaneLayout,
)
from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)
from bencher.results.render_failure import report_render_failure

try:
    from bencher.results.rerun_result import RerunResult
except ModuleNotFoundError:

    class RerunResult:  # pylint: disable=missing-class-docstring
        pass


from bencher.plugins.bench_data import BenchData, RunMeta
from bencher.plugins.builtins import (
    CALLBACK_TO_PLUGIN,
    PANES_PLUGIN_NAME,
    register_builtin_plugins,
)
from bencher.plugins.registry import decisions_to_table, get_registry
from bencher.results.dataset_result import DataSetResult
from bencher.results.histogram_result import HistogramResult
from bencher.results.holoview_results.band_result import BandResult
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.curve_result import CurveResult

# Updated imports for distribution result classes
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.holoview_results.table_result import TableResult
from bencher.results.holoview_results.tabulator_result import TabulatorResult
from bencher.results.holoview_results.xy_curve_result import XYCurveResult
from bencher.results.holoview_results.xy_hexbin_result import XYHexbinResult
from bencher.results.holoview_results.xy_histogram_result import XYHistogramResult
from bencher.results.holoview_results.xy_scatter_result import XYScatterResult
from bencher.results.optuna_result import OptunaResult
from bencher.results.pane_result import PaneResult
from bencher.results.rerun_summary import RerunSummaryResult
from bencher.results.video_summary import VideoSummaryResult
from bencher.results.volume_result import VolumeResult
from bencher.utils import AggFn, listify, resolve_aggregate

if TYPE_CHECKING:
    # Runtime import would be circular: identity imports bench_cfg, which this
    # module's own import chain pulls in.
    from bencher.identity import SweepIdentity
    from bencher.regression import RegressionResult

logger = logging.getLogger(__name__)


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
    # Late in the base list (but before their base HoloviewResult) so they never
    # shadow the earlier renderers; BenchResult must inherit them for the named-only
    # plugin callbacks (TabulatorResult.to_plot -> self.to_tabulator) to be callable
    # unbound on a BenchResult.
    TableResult,
    TabulatorResult,
    XYScatterResult,
    XYCurveResult,
    XYHistogramResult,
    XYHexbinResult,
    HoloviewResult,
    VideoSummaryResult,
    RerunSummaryResult,
    DataSetResult,
    OptunaResult,
):  # pylint: disable=too-many-ancestors
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
        # Samples that failed without aborting the sweep: raised and tolerated
        # because of run_cfg.catch, or dropped for breaking the worker contract
        # (None return / wrong-shape ResultVec — recorded unconditionally).
        self.failed_samples: list = []
        # Samples this run actually executed, set by calculate_benchmark_results.
        # Needed because neither the dataset's own size nor the job count is the
        # answer: the former grows once over_time history is merged in, and the
        # latter counts cache hits that never reached the worker.
        self.n_attempted: int = 0

    @property
    def n_failed(self) -> int:
        """How many samples raised and were tolerated.

        Tolerance without accounting is worse than fail-fast: without this a run
        in which *every* sample failed would produce an all-sentinel dataset, a
        valid-looking report and a successful exit.
        """
        # getattr, not self.failed_samples: BenchResult objects are pickled into
        # the benchmark cache, and unpickling restores __dict__ without calling
        # __init__ -- so a result cached by a pre-plan-21 bencher has no such
        # attribute at all. Reading it directly turns "upgrade, then set
        # fail_on_sample_error, then hit a warm cache" into an AttributeError.
        return len(getattr(self, "failed_samples", ()))

    @property
    def failed_fraction(self) -> float:
        """Failed samples as a fraction of the samples this run *executed*.

        Cache hits are excluded from the denominator deliberately: they never
        reached the worker and so could not have failed. Counting them would make
        one ``fail_on_sample_error`` threshold mean different things on a cold and
        a warm cache -- the single failure in a 4-sample sweep whose other 3 came
        from cache is 100% of what ran, not 25%.
        """
        attempted = getattr(self, "n_attempted", 0)  # absent on pre-plan-21 pickles
        return self.n_failed / attempted if attempted else 0.0

    def failed_samples_markdown(self, max_rows: int = 20) -> str:
        """Markdown summary of this run's failed samples, for the report.

        Bencher's contract is that a failing or contract-breaking sample never
        aborts a sweep (the expensive samples already collected must survive),
        so the report has to carry the loudness instead: this block is
        auto-inserted by :meth:`to_auto_plots` whenever ``n_failed > 0``.
        """
        attempted = getattr(self, "n_attempted", 0)
        of_attempted = f" of {attempted} executed" if attempted else ""
        lines = [
            "### ⚠ Failed samples\n",
            (
                f"**{self.n_failed}{of_attempted} sample(s) failed.** Their cells hold "
                f"the missing-value sentinel and are excluded from reductions.\n"
            ),
            "| Inputs | Error |",
            "|--------|-------|",
        ]
        failures = getattr(self, "failed_samples", ())
        for failure in failures[:max_rows]:
            inputs = ", ".join(f"{k}={v}" for k, v in failure.inputs.items()) or "—"
            # First line of the exception repr; the full traceback is in the log.
            error = failure.exception.splitlines()[0] if failure.exception else "—"
            lines.append(f"| {inputs} | {error} |")
        if len(failures) > max_rows:
            lines.append(f"\n*… and {len(failures) - max_rows} more (see the run log).*")
        return "\n".join(lines)

    @property
    def identity(self) -> SweepIdentity:
        """The keys this result was stored under, as an inspectable value.

        The config has already been through ``run_sweep``'s run_cfg merge, so no
        run config is needed here.
        """
        from bencher.identity import identity_of

        return identity_of(self.bench_cfg)

    @classmethod
    def from_existing(cls, original: BenchResult) -> BenchResult:
        new_instance = cls(original.bench_cfg)
        new_instance.ds = original.ds
        new_instance.bench_cfg = original.bench_cfg
        new_instance.plt_cnt_cfg = original.plt_cnt_cfg
        new_instance.regression_report = original.regression_report
        # A render-time cache dir override has to reach whatever object actually
        # renders the cells, and that is this one, not the original.
        new_instance.blob_cache_dir = getattr(original, "blob_cache_dir", None)
        return new_instance

    def to(
        self,
        result_type: BenchResult,
        result_var: Parameter | None = None,
        override: bool = True,
        reduce: ReduceType | None = None,
        # Aggregation controls (applied in filter())
        aggregate: bool | int | list[str] | None = None,
        agg_fn: AggFn | str = AggFn.MEAN,
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
        # getattr: a result pickled before dataset_list existed (or with it stripped)
        # must still render — the legacy read path degrades to a placeholder instead.
        result_instance.dataset_list = getattr(self, "dataset_list", [])
        result_instance.regression_report = self.regression_report
        # Same as from_existing: the override follows the object that renders.
        result_instance.blob_cache_dir = getattr(self, "blob_cache_dir", None)
        # Build kwargs for the plot call, only include reduce if explicitly set
        plot_kwargs = {
            "result_var": result_var,
            "override": override,
            "agg_over_dims": agg_over_dims,
            "agg_fn": agg_fn,
        }
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
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                row.append(report_render_failure(f"Plot plugin '{plugin.name}'", exc))
        for plot_callback in extra_callbacks:
            try:
                row.append(plot_callback(self, override=override, **kwargs))
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                row.append(report_render_failure(f"Plot callback '{plot_callback.__name__}'", exc))

        self.plt_cnt_cfg.print_debug = True
        if len(row.pane) == 0:
            row.append(pn.pane.Markdown("No Plotters are able to represent these results"))
        return row.pane

    def explain_selection(
        self,
        plot_list: list[callable | str] | None = None,
        remove_plots: list[callable | str] | None = None,
        numeric_only: bool = False,
        backend: str | None = None,
    ) -> str:
        """Why each registered plugin would or wouldn't render for this result.

        Runs the same selection `to_auto` uses (same plot_list/remove_plots
        normalization) and renders the full decision table — chosen plugins first,
        each rejected one with the first gate that dropped it (named-only, missing
        capability, shape-filter mismatch, superseded backend, ...).

        Returns:
            str: A text table, one row per registered plugin.
        """
        include_names, _ = self._normalize_plot_list(listify(plot_list))
        exclude_names, _ = self._plot_exclusions(listify(remove_plots), [], numeric_only)
        decisions = get_registry().explain(
            self.to_bench_data(),
            include=include_names,
            exclude=exclude_names or None,
            backend=backend,
        )
        return decisions_to_table(decisions)

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

        # --- Failed samples (auto-inserted whenever any sample failed) ---
        # Failures never abort a sweep (caught samples and worker-contract
        # violations alike), so the report is where they must be impossible to
        # miss — a log line is not a surface anyone reads after the fact.
        if self.n_failed:
            plot_cols.append(
                pn.pane.Markdown(
                    self.failed_samples_markdown(),
                    name="Failed Samples",
                    width=800,
                )
            )

        # --- Regression report (auto-inserted when regression detection is enabled) ---
        plot_cols.extend(self._regression_section())

        # --- Extra panels (user-injected) ---
        if extra_panels:
            for ep in extra_panels:
                try:
                    # Call only genuine factories. Excluding Viewable keeps a Viewable
                    # that defined __call__ from being invoked, while objects that are
                    # neither callable nor Viewable (a str, an hv element, a DataFrame)
                    # still fall through to append, where Column.append coerces them.
                    if callable(ep) and not isinstance(ep, pn.viewable.Viewable):
                        plot_cols.append(ep(self))
                    else:
                        plot_cols.append(ep)
                except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                    name = getattr(ep, "__name__", repr(ep))
                    plot_cols.append(report_render_failure(f"Extra panel '{name}'", exc))

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
            # Every band can be suppressed (a regression overlay above already
            # shows that variable's history), and appending the heading first
            # left it stranded over nothing. Build the bands, then decide.
            bands = self.to(BandResult, aggregate=input_names)
            if bands is not None:
                plot_cols.append(
                    pn.pane.Markdown(
                        "### Over Time\nPercentile bands across all input dimensions over time"
                    )
                )
                plot_cols.append(bands)

        kwargs.setdefault("pane_layout", self.bench_cfg.pane_layout)
        plot_cols.append(self.to_auto(**kwargs))
        plot_cols.append(self.bench_cfg.to_post_description())
        return plot_cols

    def _regression_section(self) -> list[pn.viewable.Viewable]:
        """Build the regression block as one report section, not loose panes.

        The overlays used to be appended straight into the report Column, one
        per variable, so a two-metric sweep produced two full-width plots
        stacked above everything else with nothing tying them together. Every
        other auto-generated section (``Aggregated View``, ``Over Time``) is a
        markdown heading followed by panes laid out with the sweep's
        ``pane_layout``, so this one is too: heading and summary table in one
        pane, then the per-variable overlays beside each other.

        Returns:
            list[pn.viewable.Viewable]: Panels to append, empty when regression
                detection produced nothing worth showing.
        """
        report = self.regression_report
        if report is None:
            return []

        # An overlay needs history to plot against: the absolute method has
        # none, and a first run has a report but only one over_time point.
        overlay_vars = self.regression_overlay_vars()
        plottable = [r for r in report.results if r.variable in overlay_vars]
        if not report.has_regressions and not plottable:
            return []

        regressed = len(report.regressed_variables)
        total = len(report.results)
        subtitle = (
            f"{regressed} of {total} metric(s) regressed against their history"
            if regressed
            else f"All {total} metric(s) within threshold"
        )
        panels: list[pn.viewable.Viewable] = [
            pn.pane.Markdown(
                f"### Regression\n{subtitle}\n\n{report.to_markdown()}",
                name="Regression Report",
                width=800,
            )
        ]
        if plottable:
            panels.append(self._regression_overlay_panes(plottable))
        return panels

    def _regression_overlay_panes(self, results: list[RegressionResult]) -> pn.viewable.Viewable:
        """Lay out the per-variable regression overlays like any other plot row.

        Sized from the sweep's plot_size/plot_width/plot_height so the overlays
        match the charts below them, and composed with the sweep's
        ``pane_layout`` — a row of plots under ``grid``, a tab per variable
        under ``tabs``/``tabs_and_grid`` — mirroring ``_to_panes_da``.
        """
        size = self.set_plot_size()
        overlay_kwargs = {k: size[k] for k in ("width", "height") if size.get(k) is not None}

        use_tabs = self.bench_cfg.pane_layout in (PaneLayout.tabs, PaneLayout.tabs_and_grid)
        container = ComposableContainerPanel(
            name="Regression",
            compose_method=ComposeType.sequence if use_tabs else ComposeType.right,
        )
        for r in results:
            try:
                pane = pn.pane.HoloViews(r.render_overlay(**overlay_kwargs), name=r.variable)
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                pane = report_render_failure(f"Regression overlay for '{r.variable}'", exc)
            container.append((r.variable, pane) if use_tabs else pane)
        return container.render()

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
