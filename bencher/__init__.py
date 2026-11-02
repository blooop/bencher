"""Bencher: parameter sweeps, result collection and reports.

Every public name loads on first use (PEP 562 ``__getattr__``), not at ``import
bencher``. Most of the package needs numpy, xarray, param, holoviews and panel, but
some entry points do not: :mod:`bencher.scorecard` only reads summary JSON and renders
HTML. An eager ``__init__`` made ``import bencher.scorecard`` load the whole plotting
stack, so a consumer that only renders scorecards paid for all of it.
``from bencher import X`` and ``bencher.X`` work as before; the ``TYPE_CHECKING``
block below gives type checkers and IDEs the same names, and
``test/test_lazy_init.py`` keeps it and ``_EXPORTS`` in step.
"""

import importlib
import sys
import types
import warnings

# matplotlib.projections warns at import time when it cannot import
# mpl_toolkits.mplot3d, which disables *matplotlib's* 3D projection. Bencher only
# reaches matplotlib through holoviews' matplotlib backend (regression PNG
# export) and renders its 3D plots with plotly, so the warning says nothing about
# this package -- it is import-order noise for anyone importing bencher.
warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

import typing as _typing
from typing import Any as _Any

if _typing.TYPE_CHECKING:
    from .bench_cfg import ShowMode as ShowMode
    from .bench_plot_server import BenchPlotServer as BenchPlotServer
    from .bench_report import (
        BenchReport as BenchReport,
        GithubPagesCfg as GithubPagesCfg,
        Publisher as Publisher,
    )
    from .bench_runner import BenchRunner as BenchRunner
    from .bencher import (
        Bench as Bench,
        BenchCfg as BenchCfg,
        BenchRunCfg as BenchRunCfg,
        SampleErrorPolicyError as SampleErrorPolicyError,
    )
    from .cache_management import (
        DEFAULT_CACHE_SIZE_BYTES as DEFAULT_CACHE_SIZE_BYTES,
        BlobReachability as BlobReachability,
        CacheDirStats as CacheDirStats,
        CacheStats as CacheStats,
        blob_reachability as blob_reachability,
        cache_stats as cache_stats,
        clean_orphaned_blobs as clean_orphaned_blobs,
        clean_orphaned_media as clean_orphaned_media,
        cleanup_job_media as cleanup_job_media,
        clear_all as clear_all,
        clear_media as clear_media,
        ensure_cache_version as ensure_cache_version,
        print_cache_stats as print_cache_stats,
        print_orphaned_blobs as print_orphaned_blobs,
    )
    from .claims import (
        Claim as Claim,
        Comparison as Comparison,
        Threshold as Threshold,
        Within as Within,
        parse_claim as parse_claim,
    )
    from .class_enum import ClassEnum as ClassEnum, ExampleEnum as ExampleEnum
    from .evidence import (
        EvidenceFiles as EvidenceFiles,
        ImageOutput as ImageOutput,
        evidence_markdown as evidence_markdown,
        write_evidence as write_evidence,
        write_evidence_pngs as write_evidence_pngs,
    )
    from .example.benchmark_data import ExampleBenchCfg as ExampleBenchCfg
    from .execution import Execution as Execution, execution_context as execution_context
    from .factories import create_bench as create_bench, create_bench_runner as create_bench_runner
    from .file_server import run_file_server as run_file_server
    from .git_info import git_time_event as git_time_event
    from .history import (
        HistoryEvent as HistoryEvent,
        HistoryEventKind as HistoryEventKind,
        HistoryResetError as HistoryResetError,
        OnHistoryReset as OnHistoryReset,
    )
    from .identity import (
        EXCLUDED_FIELDS as EXCLUDED_FIELDS,
        IDENTITY_FIELDS as IDENTITY_FIELDS,
        SweepIdentity as SweepIdentity,
        config_summary as config_summary,
        diff_identities as diff_identities,
        identity_of as identity_of,
        sweep_identity as sweep_identity,
    )
    from .job import (
        Executors as Executors,
        SampleFailure as SampleFailure,
        WorkerContractError as WorkerContractError,
        WorkerContractWarning as WorkerContractWarning,
        WorkerReturnedNothingError as WorkerReturnedNothingError,
    )
    from .perf_tracker import PerfReport as PerfReport, PerfTracker as PerfTracker
    from .plotting.plot_filter import PlotFilter as PlotFilter, VarRange as VarRange
    from .plugins import (
        BenchData as BenchData,
        CacheHandle as CacheHandle,
        PlotPlugin as PlotPlugin,
        PluginRegistry as PluginRegistry,
        RunMeta as RunMeta,
        get_registry as get_registry,
        plot_plugin as plot_plugin,
        register_plugin as register_plugin,
        unregister_plugin as unregister_plugin,
    )
    from .publication_target import (
        PublicationFailed as PublicationFailed,
        PublicationTarget as PublicationTarget,
    )
    from .regression import (
        MethodCells as MethodCells,
        RegressionError as RegressionError,
        RegressionReport as RegressionReport,
        RegressionResult as RegressionResult,
        method_cells as method_cells,
    )
    from .render import (
        load_result as load_result,
        render_report as render_report,
        save_result as save_result,
        save_results as save_results,
    )
    from .report_export import (
        compare_results as compare_results,
        comparison_to_json as comparison_to_json,
        result_to_dict as result_to_dict,
        result_to_json as result_to_json,
        series_for_var as series_for_var,
    )
    from .report_inventory import verify_report as verify_report
    from .results.bench_result import BenchResult as BenchResult
    from .results.composable_container.composable_container_base import (
        Axis as Axis,
        ComposableContainerBase as ComposableContainerBase,
        ComposeType as ComposeType,
        PaneLayout as PaneLayout,
    )
    from .results.composable_container.composable_container_dataframe import (
        ComposableContainerDataset as ComposableContainerDataset,
    )
    from .results.composable_container.composable_container_panel import (
        ComposableContainerPanel as ComposableContainerPanel,
    )
    from .results.composable_container.composable_container_rerun import (
        ComposableContainerRerun as ComposableContainerRerun,
        RerunRecording as RerunRecording,
        RerunViewKind as RerunViewKind,
    )
    from .results.composable_container.composable_container_video import (
        ComposableContainerVideo as ComposableContainerVideo,
        RenderCfg as RenderCfg,
    )
    from .results.dataset_result import DataSetResult as DataSetResult
    from .results.explorer_result import ExplorerResult as ExplorerResult
    from .results.histogram_result import HistogramResult as HistogramResult
    from .results.holoview_results.band_result import BandResult as BandResult
    from .results.holoview_results.bar_result import BarResult as BarResult
    from .results.holoview_results.curve_result import CurveResult as CurveResult
    from .results.holoview_results.distribution_result.box_whisker_result import (
        BoxWhiskerResult as BoxWhiskerResult,
    )
    from .results.holoview_results.distribution_result.scatter_jitter_result import (
        ScatterJitterResult as ScatterJitterResult,
    )
    from .results.holoview_results.distribution_result.violin_result import (
        ViolinResult as ViolinResult,
    )
    from .results.holoview_results.heatmap_result import HeatmapResult as HeatmapResult
    from .results.holoview_results.holoview_result import (
        HoloviewResult as HoloviewResult,
        PlotResult as PlotResult,
        ReduceType as ReduceType,
    )
    from .results.holoview_results.line_result import LineResult as LineResult
    from .results.holoview_results.scatter_result import ScatterResult as ScatterResult
    from .results.holoview_results.surface_result import SurfaceResult as SurfaceResult
    from .results.holoview_results.table_result import TableResult as TableResult
    from .results.holoview_results.tabular_spec import TabularSpec as TabularSpec
    from .results.holoview_results.tabulator_result import TabulatorResult as TabulatorResult
    from .results.holoview_results.xy_curve_result import (
        XYCurveResult as XYCurveResult,
        xy_curve as xy_curve,
    )
    from .results.holoview_results.xy_hexbin_result import (
        XYHexbinResult as XYHexbinResult,
        xy_hexbin as xy_hexbin,
    )
    from .results.holoview_results.xy_histogram_result import (
        XYHistogramResult as XYHistogramResult,
        xy_histogram as xy_histogram,
    )
    from .results.holoview_results.xy_scatter_result import (
        XYScatterResult as XYScatterResult,
        xy_scatter as xy_scatter,
    )
    from .results.optimize_result import OptimizeResult as OptimizeResult
    from .results.pane_result import PaneResult as PaneResult
    from .results.render_failure import RenderFailedWarning as RenderFailedWarning
    from .results.rerun_result import RerunResult as RerunResult
    from .results.rerun_summary import RerunSummaryResult as RerunSummaryResult
    from .results.rerun_timeline import (
        RerunTimelineResult as RerunTimelineResult,
        TimelineIndex as TimelineIndex,
    )
    from .results.svg_result import (
        MAX_SVG_FRAMES as MAX_SVG_FRAMES,
        MAX_SVG_PANELS as MAX_SVG_PANELS,
        MAX_TABLE_ROWS as MAX_TABLE_ROWS,
        SVG_STYLES as SVG_STYLES,
        SvgResult as SvgResult,
    )
    from .results.volume_result import VolumeResult as VolumeResult
    from .run import run as run
    from .sample_order import SampleOrder as SampleOrder
    from .scorecard import (
        Chrome as Chrome,
        ReportLayout as ReportLayout,
        ScorecardConfig as ScorecardConfig,
        generate_scorecard as generate_scorecard,
    )
    from .sparkline import sparkline_svg as sparkline_svg
    from .sprt import (
        Sprt as Sprt,
        SprtCfg as SprtCfg,
        SprtResult as SprtResult,
        SprtVerdict as SprtVerdict,
        sprt as sprt,
    )
    from .sweep_spec import SweepSpec as SweepSpec, diff_specs as diff_specs
    from .sweep_timings import SweepTimings as SweepTimings
    from .utils import (
        gen_image_path as gen_image_path,
        gen_path as gen_path,
        gen_rerun_data_path as gen_rerun_data_path,
        gen_video_path as gen_video_path,
        get_nearest_coords as get_nearest_coords,
        github_content as github_content,
        hmap_canonical_input as hmap_canonical_input,
        lerp as lerp,
        make_namedtuple as make_namedtuple,
        publish_file as publish_file,
        tabs_in_markdown as tabs_in_markdown,
    )
    from .utils_rerun import (
        capture_rerun_rrd as capture_rerun_rrd,
        capture_rerun_window as capture_rerun_window,
        rerun_to_pane as rerun_to_pane,
    )
    from .utils_rrd import (
        publish_and_view_rrd as publish_and_view_rrd,
        rrd_file_to_pane as rrd_file_to_pane,
        rrd_to_pane as rrd_to_pane,
    )
    from .variables.inputs import (
        BoolSweep as BoolSweep,
        EnumSweep as EnumSweep,
        FloatSweep as FloatSweep,
        IntSweep as IntSweep,
        StringSweep as StringSweep,
        SweepBase as SweepBase,
        YamlSweep as YamlSweep,
        box as box,
        p as p,
        sweep as sweep,
        with_subsampling_divisions as with_subsampling_divisions,
    )
    from .variables.parametrised_sweep import ParametrizedSweep as ParametrizedSweep
    from .variables.results import (
        SCALAR_RESULT_TYPES as SCALAR_RESULT_TYPES,
        OptDir as OptDir,
        ResultBool as ResultBool,
        ResultContainer as ResultContainer,
        ResultDataSet as ResultDataSet,
        ResultFloat as ResultFloat,
        ResultHmap as ResultHmap,
        ResultImage as ResultImage,
        ResultPath as ResultPath,
        ResultReference as ResultReference,
        ResultRerun as ResultRerun,
        ResultString as ResultString,
        ResultSVG as ResultSVG,
        ResultVar as ResultVar,
        ResultVec as ResultVec,
        ResultVideo as ResultVideo,
        curve as curve,
    )
    from .variables.singleton_parametrized_sweep import (
        ParametrizedSweepSingleton as ParametrizedSweepSingleton,
    )
    from .variables.sweep_base import (
        SUBSAMPLING_DIVISIONS_SAMPLES as SUBSAMPLING_DIVISIONS_SAMPLES,
        hash_sha1 as hash_sha1,
    )
    from .variables.time import TimeSnapshot as TimeSnapshot
    from .video_writer import VideoWriter as VideoWriter, add_image as add_image

    VideoResult = PaneResult

# Submodule (relative to this package) -> the public names it provides.
_EXPORTS: dict[str, tuple[str, ...]] = {
    ".bench_cfg": ("ShowMode",),
    ".bench_plot_server": ("BenchPlotServer",),
    ".bench_report": ("BenchReport", "GithubPagesCfg", "Publisher"),
    ".bench_runner": ("BenchRunner",),
    ".bencher": ("Bench", "BenchCfg", "BenchRunCfg", "SampleErrorPolicyError"),
    ".cache_management": (
        "BlobReachability",
        "CacheDirStats",
        "CacheStats",
        "DEFAULT_CACHE_SIZE_BYTES",
        "blob_reachability",
        "cache_stats",
        "clean_orphaned_blobs",
        "clean_orphaned_media",
        "cleanup_job_media",
        "clear_all",
        "clear_media",
        "ensure_cache_version",
        "print_cache_stats",
        "print_orphaned_blobs",
    ),
    ".claims": ("Claim", "Comparison", "Threshold", "Within", "parse_claim"),
    ".class_enum": ("ClassEnum", "ExampleEnum"),
    ".report_inventory": ("verify_report",),
    ".evidence": (
        "EvidenceFiles",
        "ImageOutput",
        "evidence_markdown",
        "write_evidence",
        "write_evidence_pngs",
    ),
    ".example.benchmark_data": ("ExampleBenchCfg",),
    ".execution": ("Execution", "execution_context"),
    ".factories": ("create_bench", "create_bench_runner"),
    ".file_server": ("run_file_server",),
    ".git_info": ("git_time_event",),
    ".history": ("HistoryEvent", "HistoryEventKind", "HistoryResetError", "OnHistoryReset"),
    ".identity": (
        "EXCLUDED_FIELDS",
        "IDENTITY_FIELDS",
        "SweepIdentity",
        "config_summary",
        "diff_identities",
        "identity_of",
        "sweep_identity",
    ),
    ".job": (
        "Executors",
        "SampleFailure",
        "WorkerContractError",
        "WorkerContractWarning",
        "WorkerReturnedNothingError",
    ),
    ".perf_tracker": ("PerfReport", "PerfTracker"),
    ".plotting.plot_filter": ("PlotFilter", "VarRange"),
    ".plugins": (
        "BenchData",
        "CacheHandle",
        "PlotPlugin",
        "PluginRegistry",
        "RunMeta",
        "get_registry",
        "plot_plugin",
        "register_plugin",
        "unregister_plugin",
    ),
    ".publication_target": ("PublicationFailed", "PublicationTarget"),
    ".regression": (
        "MethodCells",
        "RegressionError",
        "RegressionReport",
        "RegressionResult",
        "method_cells",
    ),
    ".render": ("load_result", "render_report", "save_result", "save_results"),
    ".report_export": (
        "compare_results",
        "comparison_to_json",
        "result_to_dict",
        "result_to_json",
        "series_for_var",
    ),
    ".results.bench_result": ("BenchResult",),
    ".results.composable_container.composable_container_base": (
        "Axis",
        "ComposableContainerBase",
        "ComposeType",
        "PaneLayout",
    ),
    ".results.composable_container.composable_container_dataframe": ("ComposableContainerDataset",),
    ".results.composable_container.composable_container_panel": ("ComposableContainerPanel",),
    ".results.composable_container.composable_container_rerun": (
        "ComposableContainerRerun",
        "RerunRecording",
        "RerunViewKind",
    ),
    ".results.composable_container.composable_container_video": (
        "ComposableContainerVideo",
        "RenderCfg",
    ),
    ".results.dataset_result": ("DataSetResult",),
    ".results.explorer_result": ("ExplorerResult",),
    ".results.histogram_result": ("HistogramResult",),
    ".results.holoview_results.band_result": ("BandResult",),
    ".results.holoview_results.bar_result": ("BarResult",),
    ".results.holoview_results.curve_result": ("CurveResult",),
    ".results.holoview_results.distribution_result.box_whisker_result": ("BoxWhiskerResult",),
    ".results.holoview_results.distribution_result.scatter_jitter_result": ("ScatterJitterResult",),
    ".results.holoview_results.distribution_result.violin_result": ("ViolinResult",),
    ".results.holoview_results.heatmap_result": ("HeatmapResult",),
    ".results.holoview_results.holoview_result": ("HoloviewResult", "PlotResult", "ReduceType"),
    ".results.holoview_results.line_result": ("LineResult",),
    ".results.holoview_results.scatter_result": ("ScatterResult",),
    ".results.holoview_results.surface_result": ("SurfaceResult",),
    ".results.holoview_results.table_result": ("TableResult",),
    ".results.holoview_results.tabular_spec": ("TabularSpec",),
    ".results.holoview_results.tabulator_result": ("TabulatorResult",),
    ".results.holoview_results.xy_curve_result": ("XYCurveResult", "xy_curve"),
    ".results.holoview_results.xy_hexbin_result": ("XYHexbinResult", "xy_hexbin"),
    ".results.holoview_results.xy_histogram_result": ("XYHistogramResult", "xy_histogram"),
    ".results.holoview_results.xy_scatter_result": ("XYScatterResult", "xy_scatter"),
    ".results.optimize_result": ("OptimizeResult",),
    ".results.pane_result": ("PaneResult",),
    ".results.render_failure": ("RenderFailedWarning",),
    ".results.rerun_result": ("RerunResult",),
    ".results.rerun_summary": ("RerunSummaryResult",),
    ".results.rerun_timeline": ("RerunTimelineResult", "TimelineIndex"),
    ".results.svg_result": (
        "MAX_SVG_FRAMES",
        "MAX_SVG_PANELS",
        "MAX_TABLE_ROWS",
        "SVG_STYLES",
        "SvgResult",
    ),
    ".results.volume_result": ("VolumeResult",),
    ".run": ("run",),
    ".sample_order": ("SampleOrder",),
    ".scorecard": ("Chrome", "ReportLayout", "ScorecardConfig", "generate_scorecard"),
    ".sparkline": ("sparkline_svg",),
    ".sprt": ("Sprt", "SprtCfg", "SprtResult", "SprtVerdict", "sprt"),
    ".sweep_spec": ("SweepSpec", "diff_specs"),
    ".sweep_timings": ("SweepTimings",),
    ".utils": (
        "gen_image_path",
        "gen_path",
        "gen_rerun_data_path",
        "gen_video_path",
        "get_nearest_coords",
        "github_content",
        "hmap_canonical_input",
        "lerp",
        "make_namedtuple",
        "publish_file",
        "tabs_in_markdown",
    ),
    ".utils_rrd": ("publish_and_view_rrd", "rrd_file_to_pane", "rrd_to_pane"),
    ".variables.inputs": (
        "BoolSweep",
        "EnumSweep",
        "FloatSweep",
        "IntSweep",
        "StringSweep",
        "SweepBase",
        "YamlSweep",
        "box",
        "p",
        "sweep",
        "with_subsampling_divisions",
    ),
    ".variables.parametrised_sweep": ("ParametrizedSweep",),
    ".variables.results": (
        "OptDir",
        "ResultBool",
        "ResultContainer",
        "ResultDataSet",
        "ResultFloat",
        "ResultHmap",
        "ResultImage",
        "ResultPath",
        "ResultReference",
        "ResultRerun",
        "ResultSVG",
        "ResultString",
        "ResultVar",
        "ResultVec",
        "ResultVideo",
        "SCALAR_RESULT_TYPES",
        "curve",
    ),
    ".variables.singleton_parametrized_sweep": ("ParametrizedSweepSingleton",),
    ".variables.sweep_base": ("SUBSAMPLING_DIVISIONS_SAMPLES", "hash_sha1"),
    ".variables.time": ("TimeSnapshot",),
    ".video_writer": ("VideoWriter", "add_image"),
}
_NAME_TO_MODULE = {name: module for module, names in _EXPORTS.items() for name in names}
# Public names bound to another export.
_ALIASES = {"VideoResult": "PaneResult"}
# ``bencher.utils_rerun`` is the one module that imports ``rerun`` at module scope.
_RERUN_EXPORTS = ("capture_rerun_rrd", "capture_rerun_window", "rerun_to_pane")
_DEPRECATED_ALIASES = {
    "LEVEL_SAMPLES": "SUBSAMPLING_DIVISIONS_SAMPLES",
    "with_level": "with_subsampling_divisions",
}

# So `from bencher import *` still binds every public name, as the eager __init__ did.
__all__ = [*_NAME_TO_MODULE, *_ALIASES, *_RERUN_EXPORTS]  # noqa: PLE0604


def _requires_rerun(name: str) -> type:
    """Build a stand-in for a ``rerun``-only export that is not importable.

    ``bencher.utils_rerun`` is the one module in the package that imports ``rerun`` at
    module scope, so it is the one whose names could go missing. They used to be bound
    only inside a ``try``/``except ModuleNotFoundError``: on an install without
    ``rerun-sdk`` they simply did not exist, and ``bn.capture_rerun_rrd`` raised
    ``AttributeError: module 'bencher' has no attribute ...``, naming neither the
    optional dependency nor how to get it. It also made ``bencher``'s public surface
    partial -- the state ``ty`` reports as ``possibly-missing-attribute``, which a reader
    has no way to discharge. The names now always exist; using one without the extra
    raises an ``ImportError`` that says what to install.

    A class rather than a function, so ``isinstance`` against the placeholder stays
    legal. Deliberately a *plain* class: an earlier revision gave it a metaclass whose
    ``__getattr__`` raised ``ImportError`` so attribute access would be branded too, but
    ``hasattr`` and ``getattr(x, n, default)`` only swallow ``AttributeError``, so that
    turned every defensive feature probe into an uncatchable-by-idiom crash -- on exactly
    the installs least able to diagnose it. All three names here are functions, called
    rather than read, so there is nothing for such a hook to protect.
    """
    message = (
        f"bencher.{name} requires the optional 'rerun-sdk' dependency, which is not "
        "installed. Install it with `pip install rerun-sdk`."
    )

    def __init__(_self: object, *_args: _Any, **_kwargs: _Any) -> None:  # noqa: N807 - becomes the placeholder class's __init__ via type()
        raise ImportError(message)

    return type(
        name,
        (),
        {
            "__init__": __init__,
            "__doc__": f"Placeholder for {name}; requires the optional 'rerun-sdk' package.",
        },
    )


def __getattr__(name: str) -> _Any:
    if name in _DEPRECATED_ALIASES:
        new_name = _DEPRECATED_ALIASES[name]
        warnings.warn(
            f"'{name}' is deprecated; use '{new_name}' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return getattr(sys.modules[__name__], new_name)
    if name in _ALIASES:
        value = getattr(sys.modules[__name__], _ALIASES[name])
    elif name in _NAME_TO_MODULE:
        value = getattr(importlib.import_module(_NAME_TO_MODULE[name], __name__), name)
    elif name in _RERUN_EXPORTS:
        try:
            value = getattr(importlib.import_module(".utils_rerun", __name__), name)
        except ModuleNotFoundError:
            value = _requires_rerun(name)
    elif not name.startswith("__"):
        # A submodule not imported yet: the eager __init__ imported nearly all of them,
        # so ``bencher.results.foo`` worked without an explicit import.
        try:
            return importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__name__}.{name}":
                raise
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})


# ``run`` and ``sprt`` are functions with the same names as the submodules that define
# them. Importing a submodule binds it on its parent package, so the first
# ``import bencher.run`` anywhere would replace ``bencher.run`` the function with
# ``bencher.run`` the module. The eager __init__ hid this by importing the function
# after the module; lazily, the package has to refuse that binding instead.
# test_lazy_init.py checks this is every export that shares a name with a submodule.
_SHADOWED_BY_SUBMODULE = frozenset({"run", "sprt"})


class _BencherModule(types.ModuleType):
    def __setattr__(self, name: str, value: _Any) -> None:
        if name in _SHADOWED_BY_SUBMODULE and isinstance(value, types.ModuleType):
            return
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _BencherModule
