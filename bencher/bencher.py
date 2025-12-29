import logging
from datetime import datetime
from itertools import product, combinations

from param import Parameter
from typing import Callable, List, Optional, Tuple, Any
from copy import deepcopy
import param
import xarray as xr
from diskcache import Cache
from contextlib import suppress
from functools import partial
import panel as pn

from bencher.worker_job import WorkerJob

from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.bench_plot_server import BenchPlotServer
from bencher.bench_report import BenchReport

from bencher.variables.inputs import IntSweep
from bencher.variables.results import ResultHmap
from bencher.results.bench_result import BenchResult
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.job import Job, FutureCache, JobFuture, Executors
from bencher.utils import params_to_str
from bencher.sample_order import SampleOrder

# Import helper classes
from bencher.worker_manager import WorkerManager
from bencher.result_collector import ResultCollector
from bencher.sweep_executor import SweepExecutor, worker_kwargs_wrapper

# Default cache size for benchmark results (100 GB)
DEFAULT_CACHE_SIZE_BYTES = int(100e9)

# Customize the formatter
formatter = logging.Formatter("%(levelname)s: %(message)s")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


for handler in logging.root.handlers:
    handler.setFormatter(formatter)


class Bench(BenchPlotServer):
    def __init__(
        self,
        bench_name: str | None = None,
        worker: Callable | ParametrizedSweep | None = None,
        worker_input_cfg: ParametrizedSweep | None = None,
        run_cfg: BenchRunCfg | None = None,
        report: BenchReport | None = None,
    ) -> None:
        """Create a new Bench object for benchmarking a worker function with parametrized inputs.

        This initializes a benchmarking environment that can execute and visualize the performance
        of a worker function across different parameter combinations. The worker can be either a
        callable function or a ParametrizedSweep instance with a __call__ method.

        Args:
            bench_name (str): The name of the benchmark and output folder for the figures.
                Must be a string.
            worker (Callable | ParametrizedSweep, optional): Either a function that accepts a
                ParametrizedSweep instance, or a ParametrizedSweep instance with a __call__ method.
                Defaults to None.
            worker_input_cfg (ParametrizedSweep, optional): A class defining the parameters expected
                by the worker function. Only needed if worker is a function rather than a
                ParametrizedSweep instance. Defaults to None.
            run_cfg (BenchRunCfg, optional): Configuration parameters for the benchmark run,
                such as caching settings, execution mode, etc. Defaults to None.
            report (BenchReport, optional): An existing report to append benchmark results to.
                If None, a new report will be created. Defaults to None.

        Raises:
            TypeError: If bench_name is not a string.
            RuntimeError: If worker is a class type instead of an instance.
        """
        if not isinstance(bench_name, str):
            raise TypeError(f"bench_name must be a string, got {type(bench_name).__name__}")
        self.bench_name = bench_name

        # Initialize helper classes
        self.cache_size = DEFAULT_CACHE_SIZE_BYTES
        self._worker_mgr = WorkerManager()
        self._executor = SweepExecutor(cache_size=self.cache_size)
        self._collector = ResultCollector(cache_size=self.cache_size)

        # Set worker using the manager
        self.set_worker(worker, worker_input_cfg)

        self.run_cfg = run_cfg
        if report is None:
            self.report = BenchReport(self.bench_name)
        else:
            self.report = report
            if self.report.bench_name is None:
                self.report.bench_name = self.bench_name
        self.results = []

        self.bench_cfg_hashes = []  # a list of hashes that point to benchmark results
        self.last_run_cfg = None  # cached run_cfg used to pass to the plotting function

        # Maybe put this in SweepCfg
        self.input_vars = None
        self.result_vars = None
        self.const_vars = None
        self.plot_callbacks = []
        self.plot = True

    @property
    def sample_cache(self):
        """Access the sample cache from the executor (for backward compatibility)."""
        return self._executor.sample_cache

    @sample_cache.setter
    def sample_cache(self, value):
        """Set the sample cache on the executor (for backward compatibility)."""
        self._executor.sample_cache = value

    @property
    def ds_dynamic(self):
        """Access the dynamic dataset from the collector (for backward compatibility)."""
        return self._collector.ds_dynamic

    @ds_dynamic.setter
    def ds_dynamic(self, value):
        """Set the dynamic dataset on the collector (for backward compatibility)."""
        self._collector.ds_dynamic = value

    def add_plot_callback(self, callback: Callable[[BenchResult], pn.panel], **kwargs) -> None:
        """Add a plotting callback to be called on benchmark results.

        This method registers a plotting function that will be automatically called on any
        BenchResult produced when running a sweep. You can pass additional arguments to
        the plotting function using keyword arguments.

        Args:
            callback (Callable[[BenchResult], pn.panel]): A function that takes a BenchResult
                and returns a panel object. For example: BenchResult.to_video_grid
            **kwargs: Additional keyword arguments to pass to the callback function

        Examples:
            >>> bench.add_plot_callback(BenchResult.to_video_grid, width=800)
        """
        self.plot_callbacks.append(partial(callback, **kwargs))

    def set_worker(
        self,
        worker: Callable | ParametrizedSweep,
        worker_input_cfg: ParametrizedSweep | None = None,
    ) -> None:
        """Set the benchmark worker function and its input configuration.

        This method sets up the worker function to be benchmarked. The worker can be either a
        callable function that takes a ParametrizedSweep instance or a ParametrizedSweep
        instance with a __call__ method. In the latter case, worker_input_cfg is not needed.

        Args:
            worker (Callable | ParametrizedSweep): Either a function that will be benchmarked or a
                ParametrizedSweep instance with a __call__ method. When a ParametrizedSweep is provided,
                its __call__ method becomes the worker function.
            worker_input_cfg (ParametrizedSweep, optional): The class defining the input parameters
                for the worker function. Only needed if worker is a function rather than a
                ParametrizedSweep instance. Defaults to None.

        Raises:
            RuntimeError: If worker is a class type instead of an instance.
        """
        self._worker_mgr.set_worker(worker, worker_input_cfg)
        # Expose worker attributes for backward compatibility
        self.worker = self._worker_mgr.worker
        self.worker_class_instance = self._worker_mgr.worker_class_instance
        self.worker_input_cfg = self._worker_mgr.worker_input_cfg

    def sweep_sequential(
        self,
        title: str = "",
        input_vars: List[ParametrizedSweep] | None = None,
        result_vars: List[ParametrizedSweep] | None = None,
        const_vars: List[ParametrizedSweep] | None = None,
        optimise_var: ParametrizedSweep | None = None,
        run_cfg: BenchRunCfg | None = None,
        group_size: int = 1,
        iterations: int = 1,
        relationship_cb: Callable | None = None,
        plot_callbacks: List[Callable] | bool | None = None,
    ) -> List[BenchResult]:
        """Run a sequence of benchmarks by sweeping through groups of input variables.

        This method performs sweeps on combinations of input variables, potentially
        using the optimal value from each sweep as constants for the next iteration.

        Args:
            title (str, optional): Base title for all the benchmark sweeps. Defaults to "".
            input_vars (List[ParametrizedSweep], optional): Input variables to sweep through.
                If None, defaults to all input variables from the worker class instance.
            result_vars (List[ParametrizedSweep], optional): Result variables to collect. Defaults to None.
            const_vars (List[ParametrizedSweep], optional): Variables to keep constant. Defaults to None.
            optimise_var (ParametrizedSweep, optional): Variable to optimize on each sweep iteration.
                The optimal value will be used as constant input for subsequent sweeps. Defaults to None.
            run_cfg (BenchRunCfg, optional): Run configuration. Defaults to None.
            group_size (int, optional): Number of input variables to sweep together in each run. Defaults to 1.
            iterations (int, optional): Number of optimization iterations to perform. Defaults to 1.
            relationship_cb (Callable, optional): Function to determine how to group variables for sweeping.
                Defaults to itertools.combinations if None.
            plot_callbacks (List[Callable] | bool, optional): Callbacks for plotting or bool to enable/disable.
                Defaults to None.

        Returns:
            List[BenchResult]: A list of results from all the sweep runs
        """
        if relationship_cb is None:
            relationship_cb = combinations
        if input_vars is None:
            input_vars = self.worker_class_instance.get_inputs_only()
        results = []
        for it in range(iterations):
            for input_group in relationship_cb(input_vars, group_size):
                title_gen = title + "Sweeping " + " vs ".join(params_to_str(input_group))
                if iterations > 1:
                    title_gen += f" iteration:{it}"
                res = self.plot_sweep(
                    title=title_gen,
                    input_vars=list(input_group),
                    result_vars=result_vars,
                    const_vars=const_vars,
                    run_cfg=run_cfg,
                    plot_callbacks=plot_callbacks,
                )

                if optimise_var is not None:
                    const_vars = res.get_optimal_inputs(optimise_var, True)
                results.append(res)
        return results

    def plot_sweep(
        self,
        title: str | None = None,
        input_vars: List[ParametrizedSweep] | None = None,
        result_vars: List[ParametrizedSweep] | None = None,
        const_vars: List[ParametrizedSweep] | None = None,
        time_src: datetime | None = None,
        description: str | None = None,
        post_description: str | None = None,
        pass_repeat: bool = False,
        tag: str = "",
        run_cfg: BenchRunCfg | None = None,
        plot_callbacks: List[Callable] | bool | None = None,
        sample_order: SampleOrder = SampleOrder.INORDER,
    ) -> BenchResult:
        """The all-in-one function for benchmarking and results plotting.

        This is the main function for performing benchmark sweeps. It handles all the setup,
        execution, and visualization of benchmarks based on the input parameters.

        Args:
            title (str, optional): The title of the benchmark. If None, a title will be
                generated based on the input variables. Defaults to None.
            input_vars (List[ParametrizedSweep], optional): Variables to sweep through in the benchmark.
                If None and worker_class_instance exists, uses input variables from it. Defaults to None.
            result_vars (List[ParametrizedSweep], optional): Variables to collect results for.
                If None and worker_class_instance exists, uses result variables from it. Defaults to None.
            const_vars (List[ParametrizedSweep], optional): Variables to keep constant with specified values.
                If None and worker_class_instance exists, uses default input values. Defaults to None.
            time_src (datetime, optional): The timestamp for the benchmark. Used for time-series benchmarks.
                Defaults to None, which will use the current time.
            description (str, optional): A description displayed before the benchmark plots. Defaults to None.
            post_description (str, optional): A description displayed after the benchmark plots.
                Defaults to a generic message recommending to set a custom description.
            pass_repeat (bool, optional): If True, passes the 'repeat' parameter to the worker function.
                Defaults to False.
            tag (str, optional): Tag to group different benchmarks together. Defaults to "".
            run_cfg (BenchRunCfg, optional): Configuration for how the benchmarks are run.
                If None, uses the instance's run_cfg or creates a default one. Defaults to None.
            plot_callbacks (List[Callable] | bool, optional): Callbacks for plotting results.
                If True, uses default plotting. If False, disables plotting.
                If a list, uses the provided callbacks. Defaults to None.
            sample_order (SampleOrder, optional): Controls the traversal order of sampling only.
                Defaults to SampleOrder.INORDER. Plotting and dataset dimension order are unchanged.

        Returns:
            BenchResult: An object containing all the benchmark data and results

        Raises:
            RuntimeError: If an unsupported input variable type is provided
            TypeError: If variable parameters are not of the correct type
            FileNotFoundError: If only_plot=True and no cached results exist
        """

        input_vars_in = deepcopy(input_vars)
        result_vars_in = deepcopy(result_vars)
        const_vars_in = deepcopy(const_vars)

        if self.worker_class_instance is not None:
            if input_vars_in is None:
                logging.info(
                    "No input variables passed, using all param variables in bench class as inputs"
                )
                if self.input_vars is None:
                    input_vars_in = self.worker_class_instance.get_inputs_only()
                else:
                    input_vars_in = deepcopy(self.input_vars)
                for i in input_vars_in:
                    logging.info(f"input var: {i.name}")
            if result_vars_in is None:
                logging.info(
                    "No results variables passed, using all result variables in bench class:"
                )
                if self.result_vars is None:
                    result_vars_in = self.get_result_vars(as_str=False)
                else:
                    result_vars_in = deepcopy(self.result_vars)

            if const_vars_in is None:
                if self.const_vars is None:
                    const_vars_in = self.worker_class_instance.get_input_defaults()
                else:
                    const_vars_in = deepcopy(self.const_vars)
        else:
            if input_vars_in is None:
                input_vars_in = []
            if result_vars_in is None:
                result_vars_in = []
            if const_vars_in is None:
                const_vars_in = []

        if run_cfg is None:
            if self.run_cfg is None:
                run_cfg = BenchRunCfg()
                logging.info("Generate default run cfg")
            else:
                run_cfg = deepcopy(self.run_cfg)
                logging.info("Copy run cfg from bench class")

        if run_cfg.cache.only_plot:
            run_cfg.cache.cache_results = True

        self.last_run_cfg = run_cfg

        if isinstance(input_vars_in, dict):
            input_lists = []
            for k, v in input_vars_in.items():
                param_var = self.convert_vars_to_params(k, "input", run_cfg)
                if isinstance(v, list):
                    if len(v) == 0:
                        raise ValueError(f"Input variable '{k}' cannot be an empty list")
                    param_var = param_var.with_sample_values(v)

                else:
                    raise RuntimeError("Unsupported type")
                input_lists.append(param_var)

            input_vars_in = input_lists
        else:
            for i in range(len(input_vars_in)):
                input_vars_in[i] = self.convert_vars_to_params(input_vars_in[i], "input", run_cfg)
        for i in range(len(result_vars_in)):
            result_vars_in[i] = self.convert_vars_to_params(result_vars_in[i], "result", run_cfg)

        for r in result_vars_in:
            r_name = getattr(r, "name", str(r))
            logging.info("result var: %s", r_name)

        if isinstance(const_vars_in, dict):
            const_vars_in = list(const_vars_in.items())

        for i in range(len(const_vars_in)):
            # consts come as tuple pairs
            cv_list = list(const_vars_in[i])
            cv_list[0] = self.convert_vars_to_params(cv_list[0], "const", run_cfg)
            const_vars_in[i] = cv_list

        if title is None:
            if len(input_vars_in) > 0:
                title = "Sweeping " + " vs ".join([i.name for i in input_vars_in])
            elif len(const_vars_in) > 0:
                title = "Constant Value"
                if len(const_vars_in) > 1:
                    title += "s"
                title += ": " + ", ".join([f"{c[0].name}={c[1]}" for c in const_vars_in])
            else:
                title = "Recording: " + ", ".join(
                    [getattr(i, "name", str(i)) for i in result_vars_in]
                )

        if run_cfg.execution.level > 0:
            inputs = []
            logging.debug("Input vars prior to level adjustment: %s", input_vars_in)
            if len(input_vars_in) > 0:
                for i in input_vars_in:
                    inputs.append(i.with_level(run_cfg.execution.level))
                input_vars_in = inputs

        # if any of the inputs have been include as constants, remove those variables from the list of constants
        with suppress(ValueError, AttributeError):
            for i in input_vars_in:
                for c in const_vars_in:
                    # print(i.hash_persistent())
                    if i.name == c[0].name:
                        const_vars_in.remove(c)
                        logging.info(f"removing {i.name} from constants")

        result_hmaps = []
        result_vars_only = []
        for i in result_vars_in:
            if isinstance(i, ResultHmap):
                result_hmaps.append(i)
            else:
                result_vars_only.append(i)

        if post_description is None:
            post_description = (
                "## Results Description\nPlease set post_description to explain these results"
            )

        if plot_callbacks is None:
            if self.plot_callbacks is not None and len(self.plot_callbacks) == 0:
                plot_callbacks = [BenchResult.to_auto_plots]
            else:
                plot_callbacks = self.plot_callbacks
        elif isinstance(plot_callbacks, bool):
            plot_callbacks = [BenchResult.to_auto_plots] if plot_callbacks else []

        bench_cfg = BenchCfg(
            input_vars=input_vars_in,
            result_vars=result_vars_only,
            result_hmaps=result_hmaps,
            const_vars=const_vars_in,
            bench_name=self.bench_name,
            description=description,
            post_description=post_description,
            title=title,
            pass_repeat=pass_repeat,
            tag=run_cfg.time.run_tag + tag,
            plot_callbacks=plot_callbacks,
        )
        return self.run_sweep(bench_cfg, run_cfg, time_src, sample_order)

    @staticmethod
    def filter_overridable_params(
        bench_cfg: BenchCfg, run_cfg: BenchRunCfg
    ) -> Tuple[dict, List[str], List[str]]:
        """Filter run_cfg parameters to only those that can override bench_cfg.

        Param 2.3 enforces constant Parameters (e.g. the implicit `name`), which cannot
        be overridden. This helper identifies which parameters from run_cfg can be applied
        to bench_cfg and reports any that must be skipped.

        Args:
            bench_cfg: The benchmark configuration to be updated
            run_cfg: The run configuration providing override values

        Returns:
            A tuple of (valid_params, missing_keys, constant_keys) where:
            - valid_params: dict of parameters that can be applied
            - missing_keys: list of run_cfg keys not found on bench_cfg
            - constant_keys: list of run_cfg keys that are constant on bench_cfg
        """
        bench_params = bench_cfg.param.objects()
        run_cfg_param_values = run_cfg.param.values()

        missing_keys = []
        constant_keys = []
        valid_params = {}

        for key, value in run_cfg_param_values.items():
            if key not in bench_params:
                missing_keys.append(key)
                continue

            if bench_params[key].constant:
                constant_keys.append(key)
                continue

            valid_params[key] = value

        return valid_params, missing_keys, constant_keys

    def run_sweep(
        self,
        bench_cfg: BenchCfg,
        run_cfg: BenchRunCfg,
        time_src: datetime | None = None,
        sample_order: SampleOrder = SampleOrder.INORDER,
    ) -> BenchResult:
        """Execute a benchmark sweep based on the provided configuration.

        This method handles the caching, execution, and post-processing of a benchmark sweep
        according to the provided configurations. It's typically called by `plot_sweep` rather
        than directly by users.

        Args:
            bench_cfg (BenchCfg): Configuration defining inputs, results, and other benchmark parameters
            run_cfg (BenchRunCfg): Configuration for how the benchmark should be executed
            time_src (datetime, optional): The timestamp for the benchmark. Used for time-series benchmarks.
                Defaults to None, which will use the current time.
            sample_order (SampleOrder, optional): Controls the traversal order of sampling only.
                Defaults to SampleOrder.INORDER.

        Returns:
            BenchResult: An object containing all benchmark data, results, and visualization

        Raises:
            FileNotFoundError: If only_plot=True and no cached results exist
        """
        print("tag", bench_cfg.tag)

        # Filter run_cfg parameters to only those that can override bench_cfg
        # (param 2.3 enforces constant parameters that cannot be overridden)
        run_cfg_values, missing_keys, constant_keys = self.filter_overridable_params(
            bench_cfg, run_cfg
        )

        if missing_keys:
            logging.warning(
                "Run configuration contains parameters that do not exist on "
                "the bench configuration and were ignored: %s",
                sorted(missing_keys),
            )

        if constant_keys:
            logging.warning(
                "Attempted to override constant bench parameters from run "
                "configuration; these were ignored: %s",
                sorted(constant_keys),
            )

        bench_cfg.param.update(run_cfg_values)
        bench_cfg_hash = bench_cfg.hash_persistent(True)
        bench_cfg.hash_value = bench_cfg_hash

        # does not include repeats in hash as sample_hash already includes repeat as part of the per sample hash
        bench_cfg_sample_hash = bench_cfg.hash_persistent(False)

        if self.sample_cache is None:
            self.sample_cache = self.init_sample_cache(run_cfg)
        if bench_cfg.cache.clear_sample_cache:
            self.clear_tag_from_sample_cache(bench_cfg.tag, run_cfg)

        calculate_results = True
        with Cache("cachedir/benchmark_inputs", size_limit=self.cache_size) as c:
            if run_cfg.cache.clear_cache:
                c.delete(bench_cfg_hash)
                logging.info("cleared cache")
            elif run_cfg.cache.cache_results:
                logging.info(
                    f"checking for previously calculated results with key: {bench_cfg_hash}"
                )
                if bench_cfg_hash in c:
                    logging.info(f"loading cached results from key: {bench_cfg_hash}")
                    bench_res = c[bench_cfg_hash]
                    # if not over_time:  # if over time we always want to calculate results
                    calculate_results = False
                else:
                    logging.info("did not detect results in cache")
                    if run_cfg.cache.only_plot:
                        raise FileNotFoundError("Was not able to load the results to plot!")

        if calculate_results:
            if run_cfg.time.time_event is not None:
                time_src = run_cfg.time.time_event
            bench_res = self.calculate_benchmark_results(
                bench_cfg, time_src, bench_cfg_sample_hash, run_cfg, sample_order
            )

            # use the hash of the inputs to look up historical values in the cache
            if run_cfg.time.over_time:
                bench_res.ds = self.load_history_cache(
                    bench_res.ds, bench_cfg_hash, run_cfg.time.clear_history
                )

            self.report_results(
                bench_res, run_cfg.display.print_xarray, run_cfg.display.print_pandas
            )
            self.cache_results(bench_res, bench_cfg_hash)

        logging.info(self.sample_cache.stats())
        self.sample_cache.close()

        bench_res.post_setup()

        if bench_cfg.visualization.auto_plot:
            self.report.append_result(bench_res)

        self.results.append(bench_res)
        return bench_res

    # TODO: Remove thin wrapper methods in major version bump - callers can use helpers directly
    def convert_vars_to_params(
        self,
        variable: param.Parameter | str | dict | tuple,
        var_type: str,
        run_cfg: Optional[BenchRunCfg],
    ) -> param.Parameter:
        """Convert various input formats (str, dict, tuple) to param.Parameter objects."""
        return self._executor.convert_vars_to_params(
            variable, var_type, run_cfg, self.worker_class_instance, self.worker_input_cfg
        )

    def cache_results(self, bench_res: BenchResult, bench_cfg_hash: str) -> None:
        """Cache benchmark results to disk using the config hash as key."""
        self._collector.cache_results(bench_res, bench_cfg_hash, self.bench_cfg_hashes)

    # def show(self, run_cfg: BenchRunCfg | None = None, pane: pn.panel = None) -> None:
    #     """Launch a web server with plots of the benchmark results.
    #
    #     This method starts a Panel web server to display the benchmark results interactively.
    #     It is a blocking call that runs until the server is terminated.
    #
    #     Args:
    #         run_cfg (BenchRunCfg, optional): Configuration options for the web server,
    #             such as the port number. If None, uses the instance's last_run_cfg
    #             or creates a default one. Defaults to None.
    #         pane (pn.panel, optional): A custom panel to display instead of the default
    #             benchmark visualization. Defaults to None.
    #
    #     Returns:
    #         None
    #     """
    #     if run_cfg is None:
    #         if self.last_run_cfg is not None:
    #             run_cfg = self.last_run_cfg
    #         else:
    #             run_cfg = BenchRunCfg()
    #
    #     return BenchPlotServer().plot_server(self.bench_name, run_cfg, pane)

    def load_history_cache(
        self, dataset: xr.Dataset, bench_cfg_hash: str, clear_history: bool
    ) -> xr.Dataset:
        """Load and concatenate historical benchmark data from cache."""
        return self._collector.load_history_cache(dataset, bench_cfg_hash, clear_history)

    def setup_dataset(
        self, bench_cfg: BenchCfg, time_src: datetime | str
    ) -> tuple[BenchResult, List[tuple], List[str]]:
        """Initialize n-dimensional xarray dataset for storing benchmark results."""
        return self._collector.setup_dataset(bench_cfg, time_src)

    def define_const_inputs(self, const_vars: List[Tuple[param.Parameter, Any]]) -> Optional[dict]:
        """Convert constant variable tuples into a name-value dictionary."""
        return self._executor.define_const_inputs(const_vars)

    def define_extra_vars(
        self, bench_cfg: BenchCfg, repeats: int, time_src: datetime | str
    ) -> List[IntSweep]:
        """Define meta variables (repeat count, timestamps) for benchmark tracking."""
        return self._collector.define_extra_vars(bench_cfg, repeats, time_src)

    def calculate_benchmark_results(
        self,
        bench_cfg: BenchCfg,
        time_src: datetime | str,
        bench_cfg_sample_hash: str,
        bench_run_cfg: BenchRunCfg,
        sample_order: SampleOrder = SampleOrder.INORDER,
    ) -> BenchResult:
        """Execute the benchmark runs and collect results into an n-dimensional array.

        This method handles the core benchmark execution process. It sets up the dataset,
        initializes worker jobs, submits them to the sample cache for execution or retrieval,
        and collects and stores the results.

        Args:
            bench_cfg (BenchCfg): Configuration defining the benchmark parameters
            time_src (datetime | str): Timestamp or event name for the benchmark run
            bench_cfg_sample_hash (str): Hash of the benchmark configuration without repeats
            bench_run_cfg (BenchRunCfg): Configuration for how the benchmark should be executed

        Returns:
            BenchResult: An object containing all the benchmark data and results
        """
        bench_res, func_inputs, dims_name = self.setup_dataset(bench_cfg, time_src)
        # Adjust only the sampling traversal; leave dims/plotting unchanged
        if sample_order == SampleOrder.REVERSED:
            total_dims = len(dims_name)
            num_input_dims = len(bench_res.bench_cfg.input_vars)

            # Extract coordinate values from the dataset to rebuild the Cartesian product
            dim_values = [list(bench_res.ds.coords[n].values) for n in dims_name]
            dim_indices = [list(range(len(v))) for v in dim_values]

            # Build iteration order: reverse the input portion only
            iter_order = list(range(num_input_dims))[::-1] + list(range(num_input_dims, total_dims))

            # Generate product in iter_order and map back to original order
            ordered = []
            for idx_ord, val_ord in zip(
                product(*[dim_indices[i] for i in iter_order]),
                product(*[dim_values[i] for i in iter_order]),
            ):
                idx_orig = [None] * total_dims
                val_orig = [None] * total_dims
                for j, pos in enumerate(iter_order):
                    idx_orig[pos] = idx_ord[j]
                    val_orig[pos] = val_ord[j]
                ordered.append((tuple(idx_orig), tuple(val_orig)))

            func_inputs = ordered
        bench_res.bench_cfg.hmap_kdims = sorted(dims_name)
        constant_inputs = self.define_const_inputs(bench_res.bench_cfg.const_vars)
        callcount = 1

        results_list = []
        jobs = []

        for idx_tuple, function_input_vars in func_inputs:
            job = WorkerJob(
                function_input_vars,
                idx_tuple,
                dims_name,
                constant_inputs,
                bench_cfg_sample_hash,
                bench_res.bench_cfg.tag,
            )
            job.setup_hashes()
            jobs.append(job)

            jid = f"{bench_res.bench_cfg.title}:call {callcount}/{len(func_inputs)}"
            worker = partial(worker_kwargs_wrapper, self.worker, bench_res.bench_cfg)
            cache_job = Job(
                job_id=jid,
                function=worker,
                job_args=job.function_input,
                job_key=job.function_input_signature_pure,
                tag=job.tag,
            )
            result = self.sample_cache.submit(cache_job)
            results_list.append(result)
            callcount += 1

            if bench_run_cfg.execution.executor == Executors.SERIAL:
                self.store_results(result, bench_res, job, bench_run_cfg)

        if bench_run_cfg.execution.executor != Executors.SERIAL:
            for job, res in zip(jobs, results_list):
                self.store_results(res, bench_res, job, bench_run_cfg)

        for inp in bench_res.bench_cfg.all_vars:
            self.add_metadata_to_dataset(bench_res, inp)

        return bench_res

    def store_results(
        self,
        job_result: JobFuture,
        bench_res: BenchResult,
        worker_job: WorkerJob,
        bench_run_cfg: BenchRunCfg,
    ) -> None:
        """Store worker job results into the n-dimensional result dataset."""
        self._collector.store_results(job_result, bench_res, worker_job, bench_run_cfg)

    def init_sample_cache(self, run_cfg: BenchRunCfg) -> FutureCache:
        """Initialize the FutureCache for storing benchmark function results."""
        return self._executor.init_sample_cache(run_cfg)

    def clear_tag_from_sample_cache(self, tag: str, run_cfg: BenchRunCfg) -> None:
        """Clear all cached samples matching a specific tag."""
        self._executor.clear_tag_from_sample_cache(tag, run_cfg)

    def add_metadata_to_dataset(self, bench_res: BenchResult, input_var: ParametrizedSweep) -> None:
        """Add units, long names, and descriptions to xarray dataset attributes."""
        self._collector.add_metadata_to_dataset(bench_res, input_var)

    def report_results(
        self, bench_res: BenchResult, print_xarray: bool, print_pandas: bool
    ) -> None:
        """Log benchmark results as xarray or pandas DataFrame."""
        self._collector.report_results(bench_res, print_xarray, print_pandas)

    def clear_call_counts(self) -> None:
        """Clear the worker and cache call counts, to help debug and assert caching is happening properly"""
        self.sample_cache.clear_call_counts()

    def get_result(self, index: int = -1) -> BenchResult:
        """Get a specific benchmark result from the results list.

        Args:
            index (int, optional): Index of the result to retrieve. Negative indices are supported,
                with -1 (default) returning the most recent result.

        Returns:
            BenchResult: The benchmark result at the specified index
        """
        return self.results[index]

    def get_ds(self, index: int = -1) -> xr.Dataset:
        """Get the xarray Dataset from a specific benchmark result.

        This is a convenience method that retrieves a result and returns its dataset.

        Args:
            index (int, optional): Index of the result to retrieve the dataset from.
                Negative indices are supported, with -1 (default) returning the most recent result.

        Returns:
            xr.Dataset: The xarray Dataset from the benchmark result
        """
        return self.get_result(index).to_xarray()

    def publish(self, remote_callback: Callable[[str], str]) -> str:
        """Publish the benchmark report to a remote location.

        Uses the provided callback to publish the benchmark report to a remote location
        such as a GitHub Pages site.

        Args:
            remote_callback (Callable[[str], str]): A function that takes a branch name
                and publishes the report, returning the URL where it's published

        Returns:
            str: The URL where the report has been published
        """
        branch_name = f"{self.bench_name}_{self.run_cfg.time.run_tag}"
        return self.report.publish(remote_callback, branch_name=branch_name)

    def get_result_vars(self, as_str: bool = True) -> List[str | ParametrizedSweep]:
        """
        Retrieve the result variables from the worker class instance.

        Args:
            as_str (bool): If True, the result variables are returned as strings.
                           If False, they are returned in their original form.
                           Default is True.

        Returns:
            List[str | ParametrizedSweep]: A list of result variables, either as strings or in their original form.

        Raises:
            RuntimeError: If the worker class instance is not set.
        """
        if self.worker_class_instance is not None:
            if as_str:
                return [i.name for i in self.worker_class_instance.get_results_only()]
            return self.worker_class_instance.get_results_only()
        raise RuntimeError("Worker class instance not set")

    def to(
        self,
        result_type: BenchResult,
        result_var: Optional[Parameter] = None,
        override: bool = True,
        **kwargs: Any,
    ) -> BenchResult:
        # return
        """Return the current instance of BenchResult.

        Returns:
            BenchResult: The current instance of the benchmark result
        """
        return self.get_result().to(
            result_type=result_type, result_var=result_var, override=override, **kwargs
        )

    def add(
        self,
        result_type: BenchResult,
        result_var: Optional[Parameter] = None,
        override: bool = True,
        **kwargs: Any,
    ):
        self.report.append(self.to(result_type, result_var=result_var, override=override, **kwargs))
