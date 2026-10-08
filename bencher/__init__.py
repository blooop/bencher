import warnings

# matplotlib.projections warns at import time when it cannot import
# mpl_toolkits.mplot3d, which disables *matplotlib's* 3D projection. Bencher only
# reaches matplotlib through holoviews' matplotlib backend (regression PNG
# export) and renders its 3D plots with plotly, so the warning says nothing about
# this package -- it is import-order noise for anyone importing bencher.
warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

from bencher.results.dataset_result import DataSetResult as DataSetResult
from bencher.results.explorer_result import ExplorerResult as ExplorerResult
from bencher.results.histogram_result import HistogramResult as HistogramResult
from bencher.results.holoview_results.band_result import BandResult as BandResult
from bencher.results.holoview_results.bar_result import BarResult as BarResult
from bencher.results.holoview_results.curve_result import CurveResult as CurveResult
from bencher.results.holoview_results.distribution_result.box_whisker_result import (
    BoxWhiskerResult as BoxWhiskerResult,
)
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult as ScatterJitterResult,
)
from bencher.results.holoview_results.distribution_result.violin_result import (
    ViolinResult as ViolinResult,
)
from bencher.results.holoview_results.heatmap_result import HeatmapResult as HeatmapResult
from bencher.results.holoview_results.line_result import LineResult as LineResult
from bencher.results.holoview_results.scatter_result import ScatterResult as ScatterResult
from bencher.results.holoview_results.surface_result import SurfaceResult as SurfaceResult
from bencher.results.holoview_results.table_result import TableResult as TableResult
from bencher.results.holoview_results.tabular_spec import TabularSpec as TabularSpec
from bencher.results.holoview_results.tabulator_result import TabulatorResult as TabulatorResult
from bencher.results.holoview_results.xy_curve_result import (
    XYCurveResult as XYCurveResult,
    xy_curve as xy_curve,
)
from bencher.results.holoview_results.xy_hexbin_result import (
    XYHexbinResult as XYHexbinResult,
    xy_hexbin as xy_hexbin,
)
from bencher.results.holoview_results.xy_histogram_result import (
    XYHistogramResult as XYHistogramResult,
    xy_histogram as xy_histogram,
)
from bencher.results.holoview_results.xy_scatter_result import (
    XYScatterResult as XYScatterResult,
    xy_scatter as xy_scatter,
)
from bencher.results.volume_result import VolumeResult as VolumeResult

from .bench_cfg import ShowMode as ShowMode
from .bench_plot_server import BenchPlotServer as BenchPlotServer
from .bench_runner import BenchRunner as BenchRunner
from .bencher import (
    Bench as Bench,
    BenchCfg as BenchCfg,
    BenchRunCfg as BenchRunCfg,
    SampleErrorPolicyError as SampleErrorPolicyError,
)
from .complete_report import verify_report as verify_report
from .example.benchmark_data import ExampleBenchCfg as ExampleBenchCfg
from .execution import Execution as Execution, execution_context as execution_context
from .file_server import run_file_server as run_file_server
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
    SampleFailure as SampleFailure,
    WorkerContractError as WorkerContractError,
    WorkerContractWarning as WorkerContractWarning,
    WorkerReturnedNothingError as WorkerReturnedNothingError,
)
from .publication_target import (
    PublicationFailed as PublicationFailed,
    PublicationTarget as PublicationTarget,
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
from .results.composable_container.composable_container_video import (
    ComposableContainerVideo as ComposableContainerVideo,
    RenderCfg as RenderCfg,
)
from .scorecard import (
    Chrome as Chrome,
    ReportLayout as ReportLayout,
    ScorecardConfig as ScorecardConfig,
    generate_scorecard as generate_scorecard,
)
from .sparkline import sparkline_svg as sparkline_svg
from .sweep_spec import SweepSpec as SweepSpec, diff_specs as diff_specs
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
    ResultVar as ResultVar,
    ResultVec as ResultVec,
    ResultVideo as ResultVideo,
    curve as curve,
)
from .variables.sweep_base import (
    SUBSAMPLING_DIVISIONS_SAMPLES as SUBSAMPLING_DIVISIONS_SAMPLES,
    hash_sha1 as hash_sha1,
)
from .variables.time import TimeSnapshot as TimeSnapshot


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

    def __init__(self, *_args, **_kwargs):
        raise ImportError(message)

    return type(
        name,
        (),
        {
            "__init__": __init__,
            "__doc__": f"Placeholder for {name}; requires the optional 'rerun-sdk' package.",
        },
    )


try:
    from .utils_rerun import (
        capture_rerun_rrd,
        capture_rerun_window,
        rerun_to_pane,
    )
except ModuleNotFoundError:
    capture_rerun_rrd = _requires_rerun("capture_rerun_rrd")
    capture_rerun_window = _requires_rerun("capture_rerun_window")
    rerun_to_pane = _requires_rerun("rerun_to_pane")

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
from .git_info import git_time_event as git_time_event
from .history import (
    HistoryEvent as HistoryEvent,
    HistoryEventKind as HistoryEventKind,
    HistoryResetError as HistoryResetError,
    OnHistoryReset as OnHistoryReset,
)
from .perf_tracker import PerfReport as PerfReport, PerfTracker as PerfTracker
from .plotting.plot_filter import PlotFilter as PlotFilter, VarRange as VarRange
from .regression import (
    MethodCells as MethodCells,
    RegressionError as RegressionError,
    RegressionReport as RegressionReport,
    RegressionResult as RegressionResult,
    method_cells as method_cells,
)
from .results.bench_result import BenchResult as BenchResult

# These three rerun names, plus RerunResult/RerunSummaryResult/RerunTimelineResult a few
# lines down -- six in all -- are imported unconditionally, which is a statement of fact rather than optimism.
# None of their three modules imports `rerun` at module scope; each defers it into the
# method that needs it, so an `except ModuleNotFoundError` around them never fired in any
# environment. Verified by importing `bencher` behind a `sys.meta_path` hook blocking
# `rerun`: these resolve to the real objects while utils_rerun's three become
# placeholders. `rerun_summary` could not have been optional anyway -- bench_result.py
# imports it unconditionally and `BenchResult` inherits from it. The dead handlers were
# worth deleting rather than keeping "just in case": a guard that cannot fire still has
# to be read, and this one advertised a fallback that did not exist.
# (Kept apart by import sorting; test_optional_extra_exports pins the premise.)
from .results.composable_container.composable_container_rerun import (
    ComposableContainerRerun as ComposableContainerRerun,
    RerunRecording as RerunRecording,
    RerunViewKind as RerunViewKind,
)
from .results.optimize_result import OptimizeResult as OptimizeResult
from .results.pane_result import PaneResult
from .results.render_failure import RenderFailedWarning as RenderFailedWarning
from .results.rerun_result import RerunResult as RerunResult
from .results.rerun_summary import RerunSummaryResult as RerunSummaryResult
from .results.rerun_timeline import (
    RerunTimelineResult as RerunTimelineResult,
    TimelineIndex as TimelineIndex,
)
from .sample_order import SampleOrder as SampleOrder
from .variables.parametrised_sweep import ParametrizedSweep as ParametrizedSweep
from .variables.singleton_parametrized_sweep import (
    ParametrizedSweepSingleton as ParametrizedSweepSingleton,
)

VideoResult = PaneResult
from .bench_report import (
    BenchReport as BenchReport,
    GithubPagesCfg as GithubPagesCfg,
    Publisher as Publisher,
)
from .class_enum import ClassEnum as ClassEnum, ExampleEnum as ExampleEnum
from .factories import create_bench as create_bench, create_bench_runner as create_bench_runner
from .job import Executors as Executors
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
from .results.holoview_results.holoview_result import (
    HoloviewResult as HoloviewResult,
    PlotResult as PlotResult,
    ReduceType as ReduceType,
)
from .run import run as run
from .sweep_timings import SweepTimings as SweepTimings
from .video_writer import VideoWriter as VideoWriter, add_image as add_image

_DEPRECATED_ALIASES = {
    "LEVEL_SAMPLES": "SUBSAMPLING_DIVISIONS_SAMPLES",
    "with_level": "with_subsampling_divisions",
}


def __getattr__(name: str):
    import sys

    new_name = _DEPRECATED_ALIASES.get(name)
    if new_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    warnings.warn(
        f"'{name}' is deprecated; use '{new_name}' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(sys.modules[__name__], new_name)
