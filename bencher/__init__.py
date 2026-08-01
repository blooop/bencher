import warnings

warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

from bencher.results.dataset_result import DataSetResult
from bencher.results.explorer_result import ExplorerResult
from bencher.results.histogram_result import HistogramResult
from bencher.results.holoview_results.band_result import BandResult
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.curve_result import CurveResult
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.holoview_results.table_result import TableResult
from bencher.results.holoview_results.tabular_spec import TabularSpec
from bencher.results.holoview_results.tabulator_result import TabulatorResult
from bencher.results.holoview_results.xy_curve_result import XYCurveResult, xy_curve
from bencher.results.holoview_results.xy_hexbin_result import XYHexbinResult, xy_hexbin
from bencher.results.holoview_results.xy_histogram_result import (
    XYHistogramResult,
    xy_histogram,
)
from bencher.results.holoview_results.xy_scatter_result import XYScatterResult, xy_scatter
from bencher.results.volume_result import VolumeResult

from .bench_cfg import ShowMode
from .bench_plot_server import BenchPlotServer
from .bench_runner import BenchRunner
from .bencher import Bench, BenchCfg, BenchRunCfg, SampleErrorPolicyError
from .example.benchmark_data import ExampleBenchCfg
from .file_server import run_file_server
from .identity import (
    EXCLUDED_FIELDS,
    IDENTITY_FIELDS,
    SweepIdentity,
    config_summary,
    diff_identities,
    identity_of,
    sweep_identity,
)
from .job import (
    SampleFailure,
    WorkerContractError,
    WorkerContractWarning,
    WorkerReturnedNothingError,
)
from .render import load_result, render_report, save_result
from .report_export import (
    compare_results,
    comparison_to_json,
    result_to_dict,
    result_to_json,
    series_for_var,
)
from .results.composable_container.composable_container_base import (
    Axis,
    ComposableContainerBase,
    ComposeType,
    PaneLayout,
)
from .results.composable_container.composable_container_dataframe import (
    ComposableContainerDataset,
)
from .results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)
from .results.composable_container.composable_container_video import (
    ComposableContainerVideo,
    RenderCfg,
)
from .scorecard import (
    Chrome,
    ReportLayout,
    ScorecardConfig,
    generate_scorecard,
)
from .sparkline import sparkline_svg
from .sweep_spec import SweepSpec, diff_specs
from .utils import (
    gen_image_path,
    gen_path,
    gen_rerun_data_path,
    gen_video_path,
    get_nearest_coords,
    github_content,
    hmap_canonical_input,
    lerp,
    make_namedtuple,
    publish_file,
    tabs_in_markdown,
)
from .utils_rrd import (
    publish_and_view_rrd,
    rrd_file_to_pane,
    rrd_to_pane,
)
from .variables.inputs import (
    BoolSweep,
    EnumSweep,
    FloatSweep,
    IntSweep,
    StringSweep,
    SweepBase,
    YamlSweep,
    box,
    p,
    sweep,
    with_subsampling_divisions,
)
from .variables.results import (
    SCALAR_RESULT_TYPES,
    OptDir,
    ResultBool,
    ResultContainer,
    ResultDataSet,
    ResultFloat,
    ResultHmap,
    ResultImage,
    ResultPath,
    ResultReference,
    ResultRerun,
    ResultString,
    ResultVar,
    ResultVec,
    ResultVideo,
    curve,
)
from .variables.sweep_base import SUBSAMPLING_DIVISIONS_SAMPLES, hash_sha1
from .variables.time import TimeSnapshot

try:
    from .utils_rerun import (
        capture_rerun_rrd,
        capture_rerun_window,
        rerun_to_pane,
    )
except ModuleNotFoundError:
    pass

try:
    from .results.rerun_result import RerunResult
except ModuleNotFoundError:
    pass

try:
    from .results.composable_container.composable_container_rerun import (
        ComposableContainerRerun,
        RerunRecording,
        RerunViewKind,
    )
    from .results.rerun_summary import RerunSummaryResult
except ModuleNotFoundError:
    pass


from .cache_management import (
    DEFAULT_CACHE_SIZE_BYTES,
    BlobReachability,
    CacheDirStats,
    CacheStats,
    blob_reachability,
    cache_stats,
    clean_orphaned_blobs,
    clean_orphaned_media,
    cleanup_job_media,
    clear_all,
    clear_media,
    ensure_cache_version,
    print_cache_stats,
    print_orphaned_blobs,
)
from .git_info import git_time_event
from .history import HistoryEvent, HistoryEventKind, HistoryResetError, OnHistoryReset
from .perf_tracker import PerfReport, PerfTracker
from .plotting.plot_filter import PlotFilter, VarRange
from .regression import (
    MethodCells,
    RegressionError,
    RegressionReport,
    RegressionResult,
    method_cells,
)
from .results.bench_result import BenchResult
from .results.optimize_result import OptimizeResult
from .results.pane_result import PaneResult
from .results.render_failure import RenderFailedWarning
from .sample_order import SampleOrder
from .variables.parametrised_sweep import ParametrizedSweep
from .variables.singleton_parametrized_sweep import ParametrizedSweepSingleton

VideoResult = PaneResult
from .bench_report import BenchReport, GithubPagesCfg, Publisher
from .class_enum import ClassEnum, ExampleEnum
from .factories import create_bench, create_bench_runner
from .job import Executors
from .plugins import (
    BenchData,
    CacheHandle,
    PlotPlugin,
    PluginRegistry,
    RunMeta,
    get_registry,
    plot_plugin,
    register_plugin,
    unregister_plugin,
)
from .results.holoview_results.holoview_result import HoloviewResult, ReduceType
from .run import run
from .sweep_timings import SweepTimings
from .video_writer import VideoWriter, add_image

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
