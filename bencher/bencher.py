import logging
from datetime import datetime
from itertools import product, combinations

from param import Parameter
from typing import Callable, List, Optional, Tuple, Any
from copy import deepcopy
import numpy as np
import param
import xarray as xr
from diskcache import Cache
from contextlib import suppress
from functools import partial
import panel as pn

from bencher.worker_job import WorkerJob

from bencher.bench_cfg import BenchCfg, BenchRunCfg, DimsCfg
from bencher.bench_plot_server import BenchPlotServer
from bencher.bench_report import BenchReport

from bencher.variables.inputs import IntSweep
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import (
    XARRAY_MULTIDIM_RESULT_TYPES,
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
    ResultDataSet,
)
from bencher.results.bench_result import BenchResult
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.job import Job, FutureCache, JobFuture, Executors
from bencher.utils import params_to_str

# Customize the formatter
formatter = logging.Formatter("%(levelname)s: %(message)s")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


for handler in logging.root.handlers:
    handler.setFormatter(formatter)


def set_xarray_multidim(
    data_array: xr.DataArray, index_tuple: Tuple[int, ...], value: Any
) -> xr.DataArray:
    """Set a value in a multi-dimensional xarray at the specified index position.

    This function sets a value in an N-dimensional xarray using dynamic indexing
    that works for any number of dimensions.

    Args:
        data_array (xr.DataArray): The data array to modify
        index_tuple (Tuple[int, ...]): The index coordinates as a tuple
        value (Any): The value to set at the specified position

    Returns:
        xr.DataArray: The modified data array
    """
    data_array[index_tuple] = value
    return data_array


def kwargs_to_input_cfg(worker_input_cfg: ParametrizedSweep, **kwargs) -> ParametrizedSweep:
    """Create a configured instance of a ParametrizedSweep with the provided keyword arguments.

    Args:
        worker_input_cfg (ParametrizedSweep): The ParametrizedSweep class to instantiate
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        ParametrizedSweep: A configured instance of the worker_input_cfg class
    """
    input_cfg = worker_input_cfg()
    input_cfg.param.update(kwargs)
    return input_cfg


def worker_cfg_wrapper(worker: Callable, worker_input_cfg: ParametrizedSweep, **kwargs) -> dict:
    """Wrap a worker function to accept keyword arguments instead of a config object.

    This wrapper creates an instance of the worker_input_cfg class, updates it with the
    provided keyword arguments, and passes it to the worker function.

    Args:
        worker (Callable): The worker function that expects a config object
        worker_input_cfg (ParametrizedSweep): The class defining the configuration
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        dict: The result of calling the worker function with the configured input
    """
    input_cfg = kwargs_to_input_cfg(worker_input_cfg, **kwargs)
    return worker(input_cfg)


def worker_kwargs_wrapper(worker: Callable, bench_cfg: BenchCfg, **kwargs) -> dict:
    """Prepare keyword arguments and pass them to a worker function.

    This wrapper helps filter out metadata parameters that should not be passed
    to the worker function (like 'repeat', 'over_time', and 'time_event').

    Args:
        worker (Callable): The worker function to call
        bench_cfg (BenchCfg): Benchmark configuration with parameters like pass_repeat
        **kwargs: The keyword arguments to filter and pass to the worker

    Returns:
        dict: The result from the worker function
    """
    function_input_deep = deepcopy(kwargs)
    if not bench_cfg.pass_repeat:
        function_input_deep.pop("repeat")
    if "over_time" in function_input_deep:
        function_input_deep.pop("over_time")
    if "time_event" in function_input_deep:
        function_input_deep.pop("time_event")
    return worker(**function_input_deep)


class Bench(BenchPlotServer):
    def __init__(
        self,
        bench_name: str = None,
        worker: Callable | ParametrizedSweep = None,
        worker_input_cfg: ParametrizedSweep = None,
        run_cfg: BenchRunCfg = None,
        report: BenchReport = None,
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
            AssertionError: If bench_name is not a string.
            RuntimeError: If worker is a class type instead of an instance.
        """
        assert isinstance(bench_name, str)
        self.bench_name = bench_name
        self.worker = None
        self.worker_class_instance = None
        self.worker_input_cfg = None
        self.worker_class_instance = None
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
        self.sample_cache = None  # store the results of each benchmark function call in a cache
        self.ds_dynamic = {}  # A dictionary to store unstructured vector datasets

        self.cache_size = int(100e9)  # default to 100gb

        # self.bench_cfg = BenchCfg()

        # Maybe put this in SweepCfg
        self.input_vars = None
        self.result_vars = None
        self.const_vars = None
        self.plot_callbacks = []
        self.plot = True

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
        self, worker: Callable | ParametrizedSweep, worker_input_cfg: ParametrizedSweep = None
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
        if isinstance(worker, ParametrizedSweep):
            self.worker_class_instance = worker
            # self.worker_class_type = type(worker)
            self.worker = self.worker_class_instance.__call__
            logging.info("setting worker from bench class.__call__")
        else:
            if isinstance(worker, type):
                raise RuntimeError("This should be a class instance, not a class")
            if worker_input_cfg is None:
                self.worker = worker
            else:
                self.worker = partial(worker_cfg_wrapper, worker, worker_input_cfg)
            logging.info(f"setting worker {worker}")
        self.worker_input_cfg = worker_input_cfg

    def sweep_sequential(
        self,
        title: str = "",
        input_vars: List[ParametrizedSweep] = None,
        result_vars: List[ParametrizedSweep] = None,
        const_vars: List[ParametrizedSweep] = None,
        optimise_var: ParametrizedSweep = None,
        run_cfg: BenchRunCfg = None,
        group_size: int = 1,
        iterations: int = 1,
        relationship_cb: Callable = None,
        plot_callbacks: List[Callable] | bool = None,
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
        title: str = None,
        input_vars: List[ParametrizedSweep] = None,
        result_vars: List[ParametrizedSweep] = None,
        const_vars: List[ParametrizedSweep] = None,
        time_src: datetime = None,
        description: str = None,
        post_description: str = None,
        pass_repeat: bool = False,
        tag: str = "",
        run_cfg: BenchRunCfg = None,
        plot_callbacks: List[Callable] | bool = None,
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

        if run_cfg.only_plot:
            run_cfg.cache_results = True

        self.last_run_cfg = run_cfg

        if isinstance(input_vars_in, dict):
            input_lists = []
            for k, v in input_vars_in.items():
                param_var = self.convert_vars_to_params(k, "input", run_cfg)
                if isinstance(v, list):
                    assert len(v) > 0
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
            logging.info(f"result var: {r.name}")

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
                title = "Recording: " + ", ".join([i.name for i in result_vars_in])

        if run_cfg.level > 0:
            inputs = []
            print(input_vars_in)
            if len(input_vars_in) > 0:
                for i in input_vars_in:
                    inputs.append(i.with_level(run_cfg.level))
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
            tag=run_cfg.run_tag + tag,
            plot_callbacks=plot_callbacks,
        )
        return self.run_sweep(bench_cfg, run_cfg, time_src)

    def run_sweep(
        self, bench_cfg: BenchCfg, run_cfg: BenchRunCfg, time_src: datetime = None
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

        Returns:
            BenchResult: An object containing all benchmark data, results, and visualization

        Raises:
            FileNotFoundError: If only_plot=True and no cached results exist
        """
        print("tag", bench_cfg.tag)

        bench_cfg.param.update(run_cfg.param.values())
        bench_cfg_hash = bench_cfg.hash_persistent(True)
        bench_cfg.hash_value = bench_cfg_hash

        # does not include repeats in hash as sample_hash already includes repeat as part of the per sample hash
        bench_cfg_sample_hash = bench_cfg.hash_persistent(False)

        if self.sample_cache is None:
            self.sample_cache = self.init_sample_cache(run_cfg)
        if bench_cfg.clear_sample_cache:
            self.clear_tag_from_sample_cache(bench_cfg.tag, run_cfg)

        calculate_results = True
        with Cache("cachedir/benchmark_inputs", size_limit=self.cache_size) as c:
            if run_cfg.clear_cache:
                c.delete(bench_cfg_hash)
                logging.info("cleared cache")
            elif run_cfg.cache_results:
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
                    if run_cfg.only_plot:
                        raise FileNotFoundError("Was not able to load the results to plot!")

        if calculate_results:
            if run_cfg.time_event is not None:
                time_src = run_cfg.time_event
            bench_res = self.calculate_benchmark_results(
                bench_cfg, time_src, bench_cfg_sample_hash, run_cfg
            )

            # use the hash of the inputs to look up historical values in the cache
            if run_cfg.over_time:
                bench_res.ds = self.load_history_cache(
                    bench_res.ds, bench_cfg_hash, run_cfg.clear_history
                )

            self.report_results(bench_res, run_cfg.print_xarray, run_cfg.print_pandas)
            self.cache_results(bench_res, bench_cfg_hash)

        logging.info(self.sample_cache.stats())
        self.sample_cache.close()

        bench_res.post_setup()

        if bench_cfg.auto_plot:
            self.report.append_result(bench_res)

        self.results.append(bench_res)
        return bench_res

    def convert_vars_to_params(
        self,
        variable: param.Parameter | str | dict | tuple,
        var_type: str,
        run_cfg: Optional[BenchRunCfg],
    ) -> param.Parameter:
        """Convert various input formats to param.Parameter objects.

        This method handles different ways of specifying variables in benchmark sweeps,
        including direct param.Parameter objects, string names of parameters, or dictionaries
        with parameter configuration details. It ensures all inputs are properly converted
        to param.Parameter objects with the correct configuration.

        Args:
            variable (param.Parameter | str | dict | tuple): The variable to convert, can be:
                - param.Parameter: Already a parameter object
                - str: Name of a parameter in the worker_class_instance
                - dict: Configuration with 'name' and optional 'values', 'samples', 'max_level'
                - tuple: Tuple that can be converted to a parameter
            var_type (str): Type of variable ('input', 'result', or 'const') for error messages
            run_cfg (Optional[BenchRunCfg]): Run configuration for level settings

        Returns:
            param.Parameter: The converted parameter object

        Raises:
            TypeError: If the variable cannot be converted to a param.Parameter
        """
        if isinstance(variable, str):
            variable = self.worker_class_instance.param.objects(instance=False)[variable]
        if isinstance(variable, dict):
            param_var = self.worker_class_instance.param.objects(instance=False)[variable["name"]]
            if variable.get("values"):
                param_var = param_var.with_sample_values(variable["values"])

            if variable.get("samples"):
                param_var = param_var.with_samples(variable["samples"])
            if variable.get("max_level"):
                if run_cfg is not None:
                    param_var = param_var.with_level(run_cfg.level, variable["max_level"])
            variable = param_var
        if not isinstance(variable, param.Parameter):
            raise TypeError(
                f"You need to use {var_type}_vars =[{self.worker_input_cfg}.param.your_variable], instead of {var_type}_vars =[{self.worker_input_cfg}.your_variable]"
            )
        return variable

    def cache_results(self, bench_res: BenchResult, bench_cfg_hash: str) -> None:
        """Cache benchmark results for future retrieval.

        This method stores benchmark results in the disk cache using the benchmark
        configuration hash as the key. It temporarily removes non-pickleable objects
        from the benchmark result before caching.

        Args:
            bench_res (BenchResult): The benchmark result to cache
            bench_cfg_hash (str): The hash value to use as the cache key
        """
        with Cache("cachedir/benchmark_inputs", size_limit=self.cache_size) as c:
            logging.info(f"saving results with key: {bench_cfg_hash}")
            self.bench_cfg_hashes.append(bench_cfg_hash)
            # object index may not be pickleable so remove before caching
            obj_index_tmp = bench_res.object_index
            bench_res.object_index = []

            c[bench_cfg_hash] = bench_res

            # restore object index
            bench_res.object_index = obj_index_tmp

            logging.info(f"saving benchmark: {self.bench_name}")
            c[self.bench_name] = self.bench_cfg_hashes

    # def show(self, run_cfg: BenchRunCfg = None, pane: pn.panel = None) -> None:
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
        """Load historical data from a cache if over_time is enabled.

        This method is used to retrieve and concatenate historical benchmark data from the cache
        when tracking performance over time. If clear_history is True, it will clear any existing
        historical data instead of loading it.

        Args:
            dataset (xr.Dataset): Freshly calculated benchmark data for the current run
            bench_cfg_hash (str): Hash of the input variables used to identify cached data
            clear_history (bool): If True, clears historical data instead of loading it

        Returns:
            xr.Dataset: Combined dataset with both historical and current benchmark data,
                or just the current data if no history exists or history is cleared
        """
        with Cache("cachedir/history", size_limit=self.cache_size) as c:
            if clear_history:
                logging.info("clearing history")
            else:
                logging.info(f"checking historical key: {bench_cfg_hash}")
                if bench_cfg_hash in c:
                    logging.info("loading historical data from cache")
                    ds_old = c[bench_cfg_hash]
                    dataset = xr.concat([ds_old, dataset], "over_time")
                else:
                    logging.info("did not detect any historical data")

            logging.info("saving data to history cache")
            c[bench_cfg_hash] = dataset
        return dataset

    def setup_dataset(
        self, bench_cfg: BenchCfg, time_src: datetime | str
    ) -> tuple[BenchResult, List[tuple], List[str]]:
        """Initialize an n-dimensional xarray dataset from benchmark configuration parameters.

        This function creates the data structures needed to store benchmark results based on
        the provided configuration. It sets up the xarray dimensions, coordinates, and variables
        based on input variables and result variables.

        Args:
            bench_cfg (BenchCfg): Configuration defining the benchmark parameters, inputs, and results
            time_src (datetime | str): Timestamp or event name for the benchmark run

        Returns:
            tuple[BenchResult, List[tuple], List[str]]:
                - A BenchResult object with the initialized dataset
                - A list of function input tuples (index, value pairs)
                - A list of dimension names for the dataset
        """
        if time_src is None:
            time_src = datetime.now()
        bench_cfg.meta_vars = self.define_extra_vars(bench_cfg, bench_cfg.repeats, time_src)

        bench_cfg.all_vars = bench_cfg.input_vars + bench_cfg.meta_vars
        # bench_cfg.all_vars = bench_cfg.iv_time + bench_cfg.input_vars +[ bench_cfg.iv_repeat]
        # bench_cfg.all_vars = [ bench_cfg.iv_repeat] +bench_cfg.input_vars + bench_cfg.iv_time

        for i in bench_cfg.all_vars:
            logging.info(i.sampling_str())

        dims_cfg = DimsCfg(bench_cfg)
        function_inputs = list(
            zip(product(*dims_cfg.dim_ranges_index), product(*dims_cfg.dim_ranges))
        )
        # xarray stores K N-dimensional arrays of data.  Each array is named and in this case we have an ND array for each result variable
        data_vars = {}
        dataset_list = []

        for rv in bench_cfg.result_vars:
            if isinstance(rv, (ResultVar, ResultBool)):
                result_data = np.full(dims_cfg.dims_size, np.nan, dtype=float)
                data_vars[rv.name] = (dims_cfg.dims_name, result_data)
            if isinstance(rv, (ResultReference, ResultDataSet)):
                result_data = np.full(dims_cfg.dims_size, -1, dtype=int)
                data_vars[rv.name] = (dims_cfg.dims_name, result_data)
            if isinstance(
                rv, (ResultPath, ResultVideo, ResultImage, ResultString, ResultContainer)
            ):
                result_data = np.full(dims_cfg.dims_size, "NAN", dtype=object)
                data_vars[rv.name] = (dims_cfg.dims_name, result_data)

            elif type(rv) is ResultVec:
                for i in range(rv.size):
                    result_data = np.full(dims_cfg.dims_size, np.nan)
                    data_vars[rv.index_name(i)] = (dims_cfg.dims_name, result_data)

        bench_res = BenchResult(bench_cfg)
        bench_res.ds = xr.Dataset(data_vars=data_vars, coords=dims_cfg.coords)
        bench_res.ds_dynamic = self.ds_dynamic
        bench_res.dataset_list = dataset_list
        bench_res.setup_object_index()

        return bench_res, function_inputs, dims_cfg.dims_name

    def define_const_inputs(self, const_vars: List[Tuple[param.Parameter, Any]]) -> Optional[dict]:
        """Convert constant variable tuples into a dictionary of name-value pairs.

        Args:
            const_vars (List[Tuple[param.Parameter, Any]]): List of (parameter, value) tuples
                representing constant parameters and their values

        Returns:
            Optional[dict]: Dictionary mapping parameter names to their constant values,
                or None if const_vars is None
        """
        constant_inputs = None
        if const_vars is not None:
            const_vars, constant_values = [
                [i for i, j in const_vars],
                [j for i, j in const_vars],
            ]

            constant_names = [i.name for i in const_vars]
            constant_inputs = dict(zip(constant_names, constant_values))
        return constant_inputs

    def define_extra_vars(
        self, bench_cfg: BenchCfg, repeats: int, time_src: datetime | str
    ) -> List[IntSweep]:
        """Define extra meta variables for tracking benchmark execution details.

        This function creates variables that aren't passed to the worker function but are stored
        in the n-dimensional array to provide context about the benchmark, such as the number of
        repeat measurements and timestamps.

        Args:
            bench_cfg (BenchCfg): The benchmark configuration to add variables to
            repeats (int): The number of times each sample point should be measured
            time_src (datetime | str): Either a timestamp or a string event name for temporal tracking

        Returns:
            List[IntSweep]: A list of additional parameter variables to include in the benchmark
        """
        bench_cfg.iv_repeat = IntSweep(
            default=repeats,
            bounds=[1, repeats],
            samples=repeats,
            units="repeats",
            doc="The number of times a sample was measured",
        )
        bench_cfg.iv_repeat.name = "repeat"
        extra_vars = [bench_cfg.iv_repeat]

        if bench_cfg.over_time:
            if isinstance(time_src, str):
                iv_over_time = TimeEvent(time_src)
            else:
                iv_over_time = TimeSnapshot(time_src)
            iv_over_time.name = "over_time"
            extra_vars.append(iv_over_time)
            bench_cfg.iv_time = [iv_over_time]
        return extra_vars

    def calculate_benchmark_results(
        self,
        bench_cfg: BenchCfg,
        time_src: datetime | str,
        bench_cfg_sample_hash: str,
        bench_run_cfg: BenchRunCfg,
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

            if bench_run_cfg.executor == Executors.SERIAL:
                self.store_results(result, bench_res, job, bench_run_cfg)

        if bench_run_cfg.executor != Executors.SERIAL:
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
        """Store the results from a benchmark worker job into the benchmark result dataset.

        This method handles unpacking the results from worker jobs and placing them
        in the correct locations in the n-dimensional result dataset. It supports different
        types of result variables including scalars, vectors, references, and media.

        Args:
            job_result (JobFuture): The future containing the worker function result
            bench_res (BenchResult): The benchmark result object to store results in
            worker_job (WorkerJob): The job metadata needed to index the result
            bench_run_cfg (BenchRunCfg): Configuration for how results should be handled

        Raises:
            RuntimeError: If an unsupported result variable type is encountered
        """
        result = job_result.result()
        if result is not None:
            logging.info(f"{job_result.job.job_id}:")
            if bench_res.bench_cfg.print_bench_inputs:
                for k, v in worker_job.function_input.items():
                    logging.info(f"\t {k}:{v}")

            result_dict = result if isinstance(result, dict) else result.param.values()

            for rv in bench_res.bench_cfg.result_vars:
                result_value = result_dict[rv.name]
                if bench_run_cfg.print_bench_results:
                    logging.info(f"{rv.name}: {result_value}")

                if isinstance(rv, XARRAY_MULTIDIM_RESULT_TYPES):
                    set_xarray_multidim(bench_res.ds[rv.name], worker_job.index_tuple, result_value)
                elif isinstance(rv, ResultDataSet):
                    bench_res.dataset_list.append(result_value)
                    set_xarray_multidim(
                        bench_res.ds[rv.name],
                        worker_job.index_tuple,
                        len(bench_res.dataset_list) - 1,
                    )
                elif isinstance(rv, ResultReference):
                    bench_res.object_index.append(result_value)
                    set_xarray_multidim(
                        bench_res.ds[rv.name],
                        worker_job.index_tuple,
                        len(bench_res.object_index) - 1,
                    )

                elif isinstance(rv, ResultVec):
                    if isinstance(result_value, (list, np.ndarray)):
                        if len(result_value) == rv.size:
                            for i in range(rv.size):
                                set_xarray_multidim(
                                    bench_res.ds[rv.index_name(i)],
                                    worker_job.index_tuple,
                                    result_value[i],
                                )

                else:
                    raise RuntimeError("Unsupported result type")
            for rv in bench_res.result_hmaps:
                bench_res.hmaps[rv.name][worker_job.canonical_input] = result_dict[rv.name]

            # bench_cfg.hmap = bench_cfg.hmaps[bench_cfg.result_hmaps[0].name]

    def init_sample_cache(self, run_cfg: BenchRunCfg) -> FutureCache:
        """Initialize the sample cache for storing benchmark function results.

        This method creates a FutureCache for storing and retrieving benchmark results
        based on the run configuration settings.

        Args:
            run_cfg (BenchRunCfg): Configuration with cache settings such as overwrite policy,
                executor type, and whether to cache results

        Returns:
            FutureCache: A configured cache for storing benchmark results
        """
        return FutureCache(
            overwrite=run_cfg.overwrite_sample_cache,
            executor=run_cfg.executor,
            cache_name="sample_cache",
            tag_index=True,
            size_limit=self.cache_size,
            cache_results=run_cfg.cache_samples,
        )

    def clear_tag_from_sample_cache(self, tag: str, run_cfg: BenchRunCfg) -> None:
        """Clear all samples from the cache that match a specific tag.

        This method is useful when you want to rerun a benchmark with the same tag
        but want fresh results instead of using cached data.

        Args:
            tag (str): The tag identifying samples to clear from the cache
            run_cfg (BenchRunCfg): Run configuration used to initialize the sample cache if needed
        """
        if self.sample_cache is None:
            self.sample_cache = self.init_sample_cache(run_cfg)
        self.sample_cache.clear_tag(tag)

    def add_metadata_to_dataset(self, bench_res: BenchResult, input_var: ParametrizedSweep) -> None:
        """Add variable metadata to the xarray dataset for improved visualization.

        This method adds metadata like units, long names, and descriptions to the xarray dataset
        attributes, which helps visualization tools properly label axes and tooltips.

        Args:
            bench_res (BenchResult): The benchmark result object containing the dataset to display
            input_var (ParametrizedSweep): The variable to extract metadata from
        """
        for rv in bench_res.bench_cfg.result_vars:
            if type(rv) is ResultVar:
                bench_res.ds[rv.name].attrs["units"] = rv.units
                bench_res.ds[rv.name].attrs["long_name"] = rv.name
            elif type(rv) is ResultVec:
                for i in range(rv.size):
                    bench_res.ds[rv.index_name(i)].attrs["units"] = rv.units
                    bench_res.ds[rv.index_name(i)].attrs["long_name"] = rv.name
            else:
                pass  # todo

        dsvar = bench_res.ds[input_var.name]
        dsvar.attrs["long_name"] = input_var.name
        if input_var.units is not None:
            dsvar.attrs["units"] = input_var.units
        if input_var.__doc__ is not None:
            dsvar.attrs["description"] = input_var.__doc__

    def report_results(
        self, bench_res: BenchResult, print_xarray: bool, print_pandas: bool
    ) -> None:
        """Display the calculated benchmark data in various formats.

        This method provides options to display the benchmark results as xarray data structures
        or pandas DataFrames for debugging and inspection.

        Args:
            bench_res (BenchResult): The benchmark result containing the dataset to display
            print_xarray (bool): If True, log the raw xarray Dataset structure
            print_pandas (bool): If True, log the dataset converted to a pandas DataFrame
        """
        if print_xarray:
            logging.info(bench_res.ds)
        if print_pandas:
            logging.info(bench_res.ds.to_dataframe())

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
        branch_name = f"{self.bench_name}_{self.run_cfg.run_tag}"
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
