"""Result collection and storage for benchmarking.

This module provides the ResultCollector class for managing benchmark results,
including xarray dataset operations, caching, and metadata management.
"""

import logging
from datetime import datetime
from itertools import product
from typing import Any, List, Tuple

import numpy as np
import xarray as xr
from diskcache import Cache

from bencher.bench_cfg import BenchCfg, BenchRunCfg, DimsCfg
from bencher.results.bench_result import BenchResult
from bencher.variables.inputs import IntSweep
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import (
    XARRAY_MULTIDIM_RESULT_TYPES,
    ResultVar,
    ResultBool,
    ResultVec,
    ResultPath,
    ResultVideo,
    ResultImage,
    ResultString,
    ResultContainer,
    ResultReference,
    ResultDataSet,
)
from bencher.worker_job import WorkerJob
from bencher.job import JobFuture

# Default cache size for benchmark results (100 GB)
DEFAULT_CACHE_SIZE_BYTES = int(100e9)

logger = logging.getLogger(__name__)


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


class ResultCollector:
    """Manages benchmark result collection, storage, and caching.

    This class handles the initialization of xarray datasets for storing benchmark
    results, storing results from worker jobs, managing caches, and adding metadata.

    Attributes:
        cache_size (int): Maximum size of the cache in bytes
        ds_dynamic (dict): Dictionary for storing unstructured vector datasets
    """

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE_BYTES) -> None:
        """Initialize a new ResultCollector.

        Args:
            cache_size (int): Maximum cache size in bytes. Defaults to 100 GB.
        """
        self.cache_size = cache_size
        self.ds_dynamic: dict = {}

    def setup_dataset(
        self, bench_cfg: BenchCfg, time_src: datetime | str
    ) -> Tuple[BenchResult, List[Tuple], List[str]]:
        """Initialize an n-dimensional xarray dataset from benchmark configuration parameters.

        This function creates the data structures needed to store benchmark results based on
        the provided configuration. It sets up the xarray dimensions, coordinates, and variables
        based on input variables and result variables.

        Args:
            bench_cfg (BenchCfg): Configuration defining the benchmark parameters, inputs, and
                results
            time_src (datetime | str): Timestamp or event name for the benchmark run

        Returns:
            Tuple[BenchResult, List[Tuple], List[str]]:
                - A BenchResult object with the initialized dataset
                - A list of function input tuples (index, value pairs)
                - A list of dimension names for the dataset
        """
        if time_src is None:
            time_src = datetime.now()
        bench_cfg.meta_vars = self.define_extra_vars(
            bench_cfg, bench_cfg.execution.repeats, time_src
        )

        bench_cfg.all_vars = bench_cfg.input_vars + bench_cfg.meta_vars

        for i in bench_cfg.all_vars:
            logger.info(i.sampling_str())

        dims_cfg = DimsCfg(bench_cfg)
        function_inputs = list(
            zip(product(*dims_cfg.dim_ranges_index), product(*dims_cfg.dim_ranges))
        )
        # xarray stores K N-dimensional arrays of data.
        # Each array is named and in this case we have an ND array for each result variable
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
            time_src (datetime | str): Either a timestamp or a string event name for temporal
                tracking

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

        if bench_cfg.time.over_time:
            if isinstance(time_src, str):
                iv_over_time = TimeEvent(time_src)
            else:
                iv_over_time = TimeSnapshot(time_src)
            iv_over_time.name = "over_time"
            extra_vars.append(iv_over_time)
            bench_cfg.iv_time = [iv_over_time]
        return extra_vars

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
            logger.info(f"{job_result.job.job_id}:")
            if bench_res.bench_cfg.display.print_bench_inputs:
                for k, v in worker_job.function_input.items():
                    logger.info(f"\t {k}:{v}")

            result_dict = result if isinstance(result, dict) else result.param.values()

            for rv in bench_res.bench_cfg.result_vars:
                result_value = result_dict[rv.name]
                if bench_run_cfg.display.print_bench_results:
                    logger.info(f"{rv.name}: {result_value}")

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

    def cache_results(
        self, bench_res: BenchResult, bench_cfg_hash: str, bench_cfg_hashes: List[str]
    ) -> None:
        """Cache benchmark results for future retrieval.

        This method stores benchmark results in the disk cache using the benchmark
        configuration hash as the key. It temporarily removes non-pickleable objects
        from the benchmark result before caching.

        Args:
            bench_res (BenchResult): The benchmark result to cache
            bench_cfg_hash (str): The hash value to use as the cache key
            bench_cfg_hashes (List[str]): List to append the hash to (modified in place)
        """
        with Cache("cachedir/benchmark_inputs", size_limit=self.cache_size) as c:
            logger.info(f"saving results with key: {bench_cfg_hash}")
            bench_cfg_hashes.append(bench_cfg_hash)
            # object index may not be pickleable so remove before caching
            obj_index_tmp = bench_res.object_index
            bench_res.object_index = []

            c[bench_cfg_hash] = bench_res

            # restore object index
            bench_res.object_index = obj_index_tmp

            logger.info(f"saving benchmark: {bench_res.bench_cfg.bench_name}")
            c[bench_res.bench_cfg.bench_name] = bench_cfg_hashes

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
                logger.info("clearing history")
            else:
                logger.info(f"checking historical key: {bench_cfg_hash}")
                if bench_cfg_hash in c:
                    logger.info("loading historical data from cache")
                    ds_old = c[bench_cfg_hash]
                    dataset = xr.concat([ds_old, dataset], "over_time")
                else:
                    logger.info("did not detect any historical data")

            logger.info("saving data to history cache")
            c[bench_cfg_hash] = dataset
        return dataset

    def add_metadata_to_dataset(self, bench_res: BenchResult, input_var: Any) -> None:
        """Add variable metadata to the xarray dataset for improved visualization.

        This method adds metadata like units, long names, and descriptions to the xarray dataset
        attributes, which helps visualization tools properly label axes and tooltips.

        Args:
            bench_res (BenchResult): The benchmark result object containing the dataset to display
            input_var: The variable to extract metadata from
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
            logger.info(bench_res.ds)
        if print_pandas:
            logger.info(bench_res.ds.to_dataframe())
