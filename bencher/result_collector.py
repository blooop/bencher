"""Result collection and storage for benchmarking.

This module provides the ResultCollector class for managing benchmark results,
including xarray dataset operations, caching, and metadata management.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from itertools import product
from typing import Any

import numpy as np
import xarray as xr
from diskcache import Cache

from bencher.bench_cfg import BenchCfg, BenchRunCfg, DimsCfg
from bencher.results.bench_result import BenchResult
from bencher.variables.inputs import IntSweep
from bencher.variables.time import TimeSnapshot, TimeEvent
from bencher.variables.results import (
    XARRAY_MULTIDIM_RESULT_TYPES,
    SCALAR_RESULT_TYPES,
    ResultFloat,
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
    data_array: xr.DataArray, index_tuple: tuple[int, ...], value: Any
) -> xr.DataArray:
    """Set a value in a multi-dimensional xarray at the specified index position.

    This function sets a value in an N-dimensional xarray using dynamic indexing
    that works for any number of dimensions.

    Args:
        data_array (xr.DataArray): The data array to modify
        index_tuple (tuple[int, ...]): The index coordinates as a tuple
        value (Any): The value to set at the specified position

    Returns:
        xr.DataArray: The modified data array
    """
    data_array.values[index_tuple] = value
    return data_array


def _set_result_value(
    bench_res: "BenchResult",
    rv_arrays: dict[str, np.ndarray] | None,
    name: str,
    idx: tuple,
    value: Any,
) -> None:
    """Write a single result value, using pre-cached numpy arrays when available."""
    if rv_arrays is not None:
        rv_arrays[name][idx] = value
    else:
        set_xarray_multidim(bench_res.ds[name], idx, value)


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
        self._benchmark_cache: Cache | None = None
        self._history_cache: Cache | None = None

    def get_benchmark_cache(self) -> Cache:
        """Return the persistent benchmark_inputs Cache, creating it on first access."""
        if self._benchmark_cache is None:
            self._benchmark_cache = Cache("cachedir/benchmark_inputs", size_limit=self.cache_size)
        return self._benchmark_cache

    def get_history_cache(self) -> Cache:
        """Return the persistent history Cache, creating it on first access."""
        if self._history_cache is None:
            self._history_cache = Cache("cachedir/history", size_limit=self.cache_size)
        return self._history_cache

    def close_caches(self) -> None:
        """Close any open cache instances. Safe to call multiple times."""
        if self._benchmark_cache is not None:
            self._benchmark_cache.close()
            self._benchmark_cache = None
        if self._history_cache is not None:
            self._history_cache.close()
            self._history_cache = None

    def __enter__(self) -> "ResultCollector":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close_caches()

    def setup_dataset(
        self, bench_cfg: BenchCfg, time_src: datetime | str
    ) -> tuple[BenchResult, zip, list[str], int]:
        """Initialize an n-dimensional xarray dataset from benchmark configuration parameters.

        This function creates the data structures needed to store benchmark results based on
        the provided configuration. It sets up the xarray dimensions, coordinates, and variables
        based on input variables and result variables.

        Args:
            bench_cfg (BenchCfg): Configuration defining the benchmark parameters, inputs, and
                results
            time_src (datetime | str): Timestamp or event name for the benchmark run

        Returns:
            tuple[BenchResult, zip, list[str], int]:
                - A BenchResult object with the initialized dataset
                - A lazy iterator of function input tuples (index, value pairs)
                - A list of dimension names for the dataset
                - The total number of jobs (Cartesian product size)
        """
        if time_src is None:
            time_src = datetime.now()
        bench_cfg.meta_vars = self.define_extra_vars(bench_cfg, bench_cfg.repeats, time_src)

        bench_cfg.all_vars = bench_cfg.input_vars + bench_cfg.meta_vars

        for i in bench_cfg.all_vars:
            logger.info(i.sampling_str())

        dims_cfg = DimsCfg(bench_cfg)
        total_jobs = math.prod(dims_cfg.dims_size)
        function_inputs = zip(product(*dims_cfg.dim_ranges_index), product(*dims_cfg.dim_ranges))
        # xarray stores K N-dimensional arrays of data.
        # Each array is named and in this case we have an ND array for each result variable
        data_vars = {}
        dataset_list = []

        for rv in bench_cfg.result_vars:
            if isinstance(rv, SCALAR_RESULT_TYPES):
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

        return bench_res, function_inputs, dims_cfg.dims_name, total_jobs

    def define_extra_vars(
        self, bench_cfg: BenchCfg, repeats: int, time_src: datetime | str
    ) -> list[IntSweep]:
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
            list[IntSweep]: A list of additional parameter variables to include in the benchmark
        """
        bench_cfg.iv_repeat = IntSweep(
            default=repeats,
            bounds=[1, repeats],
            samples=repeats,
            units="repeats",
            doc="The number of times a sample was measured",
            optimize=False,
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

    @staticmethod
    def precompute_result_arrays(bench_res: BenchResult) -> dict[str, np.ndarray]:
        """Pre-fetch the underlying numpy arrays for all result variables.

        This avoids repeated xarray Dataset.__getitem__ lookups (which trigger
        _construct_dataarray) during the per-job store loop.  The returned arrays
        are views into the dataset, so writes go directly into bench_res.ds.
        """
        rv_arrays: dict[str, np.ndarray] = {}
        for rv in bench_res.bench_cfg.result_vars:
            if isinstance(rv, ResultVec):
                for i in range(rv.size):
                    rv_arrays[rv.index_name(i)] = bench_res.ds[rv.index_name(i)].values
            else:
                rv_arrays[rv.name] = bench_res.ds[rv.name].values
        return rv_arrays

    def store_results(
        self,
        job_result: JobFuture,
        bench_res: BenchResult,
        worker_job: WorkerJob,
        bench_run_cfg: BenchRunCfg,
        rv_arrays: dict[str, np.ndarray] | None = None,
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
            rv_arrays (dict, optional): Pre-computed numpy arrays from
                precompute_result_arrays(). Falls back to dataset lookup if None.

        Raises:
            RuntimeError: If an unsupported result variable type is encountered
        """
        result = job_result.result()
        if result is not None:
            logger.info(f"{job_result.job.job_id}:")
            if bench_res.bench_cfg.print_bench_inputs:
                for k, v in worker_job.function_input.items():
                    logger.info(f"\t {k}:{v}")

            result_dict = result if isinstance(result, dict) else result.param.values()
            idx = worker_job.index_tuple

            for rv in bench_res.bench_cfg.result_vars:
                try:
                    result_value = result_dict[rv.name]
                except KeyError:
                    available = list(result_dict.keys())
                    raise KeyError(
                        f"Result variable '{rv.name}' was not set by the "
                        f"benchmark function. Available keys: {available}. "
                        f"Make sure your benchmark() method sets "
                        f"self.{rv.name}."
                    ) from None
                if bench_run_cfg.print_bench_results:
                    logger.info(f"{rv.name}: {result_value}")

                if isinstance(rv, XARRAY_MULTIDIM_RESULT_TYPES):
                    _set_result_value(bench_res, rv_arrays, rv.name, idx, result_value)
                elif isinstance(rv, ResultDataSet):
                    bench_res.dataset_list.append(result_value)
                    _set_result_value(
                        bench_res, rv_arrays, rv.name, idx, len(bench_res.dataset_list) - 1
                    )
                elif isinstance(rv, ResultReference):
                    bench_res.object_index.append(result_value)
                    _set_result_value(
                        bench_res, rv_arrays, rv.name, idx, len(bench_res.object_index) - 1
                    )

                elif isinstance(rv, ResultVec):
                    if isinstance(result_value, (list, np.ndarray)):
                        if len(result_value) == rv.size:
                            for i in range(rv.size):
                                _set_result_value(
                                    bench_res, rv_arrays, rv.index_name(i), idx, result_value[i]
                                )

                else:
                    raise RuntimeError("Unsupported result type")
            for rv in bench_res.result_hmaps:
                bench_res.hmaps[rv.name][worker_job.canonical_input] = result_dict[rv.name]

    def cache_results(
        self, bench_res: BenchResult, bench_cfg_hash: str, bench_cfg_hashes: list[str]
    ) -> None:
        """Cache benchmark results for future retrieval.

        This method stores benchmark results in the disk cache using the benchmark
        configuration hash as the key. It temporarily removes non-pickleable objects
        from the benchmark result before caching.

        Args:
            bench_res (BenchResult): The benchmark result to cache
            bench_cfg_hash (str): The hash value to use as the cache key
            bench_cfg_hashes (list[str]): List to append the hash to (modified in place)
        """
        c = self.get_benchmark_cache()
        logger.info(f"saving results with key: {bench_cfg_hash}")
        bench_cfg_hashes.append(bench_cfg_hash)
        # object index may not be pickleable so remove before caching
        obj_index_tmp = bench_res.object_index
        bench_res.object_index = []
        try:
            c[bench_cfg_hash] = bench_res
        finally:
            # restore object index even if the cache write fails
            bench_res.object_index = obj_index_tmp

        logger.info(f"saving benchmark: {bench_res.bench_cfg.bench_name}")
        c[bench_res.bench_cfg.bench_name] = bench_cfg_hashes

    def load_history_cache(
        self,
        dataset: xr.Dataset,
        bench_cfg_hash: str,
        clear_history: bool,
        max_time_events: int | None = None,
    ) -> xr.Dataset:
        """Load historical data from a cache if over_time is enabled.

        This method is used to retrieve and concatenate historical benchmark data from the cache
        when tracking performance over time. If clear_history is True, it will clear any existing
        historical data instead of loading it.

        Args:
            dataset (xr.Dataset): Freshly calculated benchmark data for the current run
            bench_cfg_hash (str): Hash of the input variables used to identify cached data
            clear_history (bool): If True, clears historical data instead of loading it
            max_time_events (int | None): Maximum number of over_time events to retain.
                Oldest events are trimmed. None means unlimited.

        Returns:
            xr.Dataset: Combined dataset with both historical and current benchmark data,
                or just the current data if no history exists or history is cleared
        """
        c = self.get_history_cache()
        if clear_history:
            logger.info("clearing history")
        else:
            logger.info(f"checking historical key: {bench_cfg_hash}")
            if bench_cfg_hash in c:
                logger.info("loading historical data from cache")
                ds_old = c[bench_cfg_hash]
                if (
                    "over_time" in ds_old.dims
                    and "over_time" in dataset.dims
                    and ds_old["over_time"].dtype != dataset["over_time"].dtype
                ):
                    logger.warning(
                        "Discarding incompatible historical data "
                        "(over_time dtype changed: "
                        f"{ds_old['over_time'].dtype} -> {dataset['over_time'].dtype})"
                    )
                else:
                    dataset = xr.concat([ds_old, dataset], "over_time")
            else:
                logger.info("did not detect any historical data")

        if max_time_events is not None and "over_time" in dataset.dims:
            if dataset.sizes["over_time"] > max_time_events:
                dataset = dataset.isel(over_time=slice(-max_time_events, None))

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
            if isinstance(rv, ResultFloat):
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
