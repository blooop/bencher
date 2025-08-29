from .bencher import Bench, BenchCfg, BenchRunCfg
from .bench_runner import BenchRunner
from .example.benchmark_data import (
    ExampleBenchCfgIn,
    ExampleBenchCfgOut,
    bench_function,
)
from .bench_plot_server import BenchPlotServer
from .variables.sweep_base import hash_sha1
from .variables.inputs import (
    IntSweep,
    FloatSweep,
    StringSweep,
    EnumSweep,
    BoolSweep,
    SweepBase,
)
from .variables.time import TimeSnapshot

from .variables.inputs import box, p
from .variables.results import (
    ResultVar,
    ResultBool,
    ResultVec,
    ResultHmap,
    ResultPath,
    ResultVideo,
    ResultImage,
    ResultString,
    ResultContainer,
    ResultReference,
    ResultVolume,
    OptDir,
    ResultDataSet,
    curve,
)

from .results.composable_container.composable_container_base import (
    ComposeType,
    ComposableContainerBase,
)
from .results.composable_container.composable_container_video import (
    ComposableContainerVideo,
    RenderCfg,
)

from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.curve_result import CurveResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.holoview_results.tabulator_result import TabulatorResult
from bencher.results.holoview_results.table_result import TableResult

from bencher.results.histogram_result import HistogramResult
from bencher.results.explorer_result import ExplorerResult
from bencher.results.dataset_result import DataSetResult

from .utils import (
    hmap_canonical_input,
    get_nearest_coords,
    make_namedtuple,
    gen_path,
    gen_image_path,
    gen_video_path,
    gen_rerun_data_path,
    lerp,
    tabs_in_markdown,
    publish_file,
    github_content,
)

try:
    from .utils_rerun import publish_and_view_rrd, rrd_to_pane, capture_rerun_window
    from .flask_server import run_flask_in_thread
except ModuleNotFoundError as e:
    pass


from .plotting.plot_filter import VarRange, PlotFilter
from .variables.parametrised_sweep import ParametrizedSweep
from .caching import CachedParams
from .results.bench_result import BenchResult
from .results.video_result import VideoResult
from .results.holoview_results.holoview_result import ReduceType, HoloviewResult
from .bench_report import BenchReport, GithubPagesCfg
from .job import Executors
from .video_writer import VideoWriter, add_image
from .class_enum import ClassEnum, ExampleEnum
