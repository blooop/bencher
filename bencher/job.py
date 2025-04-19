from __future__ import annotations
from typing import Callable
import logging
from diskcache import Cache
from concurrent.futures import Future, ProcessPoolExecutor
from .utils import hash_sha1
from strenum import StrEnum
from enum import auto

try:
    from scoop import futures as scoop_future_executor
except ImportError as e:
    scoop_future_executor = None


class Job:
    """Represents a benchmarking job to be executed or retrieved from cache.

    A Job encapsulates a function, its arguments, and metadata for caching
    and tracking purposes.

    Attributes:
        job_id (str): A unique identifier for the job, used for logging
        function (Callable): The function to be executed
        job_args (dict): Arguments to pass to the function
        job_key (str): A hash key for caching, derived from job_args if not provided
        tag (str): Optional tag for grouping related jobs
    """

    def __init__(
        self, job_id: str, function: Callable, job_args: dict, job_key: str = None, tag: str = ""
    ) -> None:
        """Initialize a Job with function and arguments.

        Args:
            job_id (str): A unique identifier for this job
            function (Callable): The function to execute
            job_args (dict): Arguments to pass to the function
            job_key (str, optional): Cache key for this job. If None, will be generated
                from job_args. Defaults to None.
            tag (str, optional): Tag for grouping related jobs. Defaults to "".
        """
        self.job_id = job_id
        self.function = function
        self.job_args = job_args
        if job_key is None:
            self.job_key = hash_sha1(tuple(sorted(self.job_args.items())))
        else:
            self.job_key = job_key
        self.tag = tag


class JobFuture:
    """A wrapper for a job result or future that handles caching.

    This class provides a unified interface for handling both immediate results
    and futures (for asynchronous execution). It also handles caching results
    when they become available.

    Attributes:
        job (Job): The job this future corresponds to
        res (dict): The result, if available immediately
        future (Future): The future representing the pending job, if executed asynchronously
        cache: The cache to store results in when they become available
    """

    def __init__(self, job: Job, res: dict = None, future: Future = None, cache=None) -> None:
        """Initialize a JobFuture with either an immediate result or a future.

        Args:
            job (Job): The job this future corresponds to
            res (dict, optional): The immediate result, if available. Defaults to None.
            future (Future, optional): The future representing the pending result. Defaults to None.
            cache (Cache, optional): The cache to store results in. Defaults to None.

        Raises:
            AssertionError: If neither res nor future is provided
        """
        self.job = job
        self.res = res
        self.future = future
        # either a result or a future needs to be passed
        assert self.res is not None or self.future is not None, (
            "make sure you are returning a dict or super().__call__(**kwargs) from your __call__ function"
        )

        self.cache = cache

    def result(self) -> dict:
        """Get the job result, waiting for completion if necessary.

        If the result is not immediately available (i.e., it's a future),
        this method will wait for the future to complete. Once the result
        is available, it will be cached if a cache is provided.

        Returns:
            dict: The job result
        """
        if self.future is not None:
            self.res = self.future.result()
        if self.cache is not None and self.res is not None:
            self.cache.set(self.job.job_key, self.res, tag=self.job.tag)
        return self.res


def run_job(job: Job) -> dict:
    """Execute a job by calling its function with the provided arguments.

    This is a helper function used primarily by executors to run jobs.

    Args:
        job (Job): The job to execute

    Returns:
        dict: The result of the job execution
    """
    result = job.function(**job.job_args)
    return result


class Executors(StrEnum):
    """Enumeration of available execution strategies for benchmark jobs.

    This enum defines the execution modes for running benchmark jobs
    and provides a factory method to create appropriate executors.
    """

    SERIAL = auto()  # slow but reliable
    MULTIPROCESSING = auto()  # breaks for large number of futures
    SCOOP = auto()  # requires running with python -m scoop your_file.py
    # THREADS=auto() #not that useful as most bench code is cpu bound

    @staticmethod
    def factory(provider: "Executors") -> Future | None:
        """Create an executor instance based on the specified execution strategy.

        Args:
            provider (Executors): The type of executor to create

        Returns:
            Future | None: The executor instance, or None for serial execution
        """
        providers = {
            Executors.SERIAL: None,
            Executors.MULTIPROCESSING: ProcessPoolExecutor(),
            Executors.SCOOP: scoop_future_executor,
        }
        return providers[provider]


class FutureCache:
    """A cache system for benchmark job results with executor support.

    This class provides a unified interface for running benchmark jobs either serially
    or in parallel, with optional caching of results. It manages the execution strategy,
    caching policy, and tracks statistics about job execution.

    Attributes:
        executor_type (Executors): The execution strategy to use
        executor: The executor instance, created on demand
        cache (Cache): Cache for storing job results
        overwrite (bool): Whether to overwrite existing cached results
        call_count (int): Counter for job calls
        size_limit (int): Maximum size of the cache in bytes
        worker_wrapper_call_count (int): Number of job submissions
        worker_fn_call_count (int): Number of actual function executions
        worker_cache_call_count (int): Number of cache hits
    """

    def __init__(
        self,
        executor=Executors.SERIAL,
        overwrite: bool = True,
        cache_name: str = "fcache",
        tag_index: bool = True,
        size_limit: int = int(20e9),  # 20 GB
        cache_results: bool = True,
    ):
        """Initialize a FutureCache with optional caching and execution settings.

        Args:
            executor (Executors, optional): The execution strategy to use. Defaults to Executors.SERIAL.
            overwrite (bool, optional): Whether to overwrite existing cached results. Defaults to True.
            cache_name (str, optional): Base name for the cache directory. Defaults to "fcache".
            tag_index (bool, optional): Whether to enable tag-based indexing in the cache. Defaults to True.
            size_limit (int, optional): Maximum size of the cache in bytes. Defaults to 20GB.
            cache_results (bool, optional): Whether to cache results at all. Defaults to True.
        """
        self.executor_type = executor
        self.executor = None
        if cache_results:
            self.cache = Cache(f"cachedir/{cache_name}", tag_index=tag_index, size_limit=size_limit)
            logging.info(f"cache dir: {self.cache.directory}")
        else:
            self.cache = None

        self.overwrite = overwrite
        self.call_count = 0
        self.size_limit = size_limit

        self.worker_wrapper_call_count = 0
        self.worker_fn_call_count = 0
        self.worker_cache_call_count = 0

    def submit(self, job: Job) -> JobFuture:
        """Submit a job for execution, with caching if enabled.

        This method first checks if the job result is already in the cache (if caching is enabled
        and overwrite is False). If not found in the cache, it executes the job either serially
        or using the configured executor.

        Args:
            job (Job): The job to submit

        Returns:
            JobFuture: A future representing the job execution
        """
        self.worker_wrapper_call_count += 1

        if self.cache is not None:
            if not self.overwrite and job.job_key in self.cache:
                logging.info(f"Found job: {job.job_id} in cache, loading...")
                # logging.info(f"Found key: {job.job_key} in cache")
                self.worker_cache_call_count += 1
                return JobFuture(
                    job=job,
                    res=self.cache[job.job_key],
                )

        self.worker_fn_call_count += 1

        if self.executor_type is not Executors.SERIAL:
            if self.executor is None:
                self.executor = Executors.factory(self.executor_type)
        if self.executor is not None:
            self.overwrite_msg(job, " starting parallel job...")
            return JobFuture(
                job=job,
                future=self.executor.submit(run_job, job),
                cache=self.cache,
            )
        self.overwrite_msg(job, " starting serial job...")
        return JobFuture(
            job=job,
            res=run_job(job),
            cache=self.cache,
        )

    def overwrite_msg(self, job: Job, suffix: str) -> None:
        """Log a message about overwriting or using cache.

        Args:
            job (Job): The job being executed
            suffix (str): Additional text to add to the log message
        """
        msg = "OVERWRITING" if self.overwrite else "NOT in"
        logging.info(f"{job.job_id} {msg} cache{suffix}")

    def clear_call_counts(self) -> None:
        """Clear the worker and cache call counts, to help debug and assert caching is happening properly."""
        self.worker_wrapper_call_count = 0
        self.worker_fn_call_count = 0
        self.worker_cache_call_count = 0

    def clear_cache(self) -> None:
        """Clear all entries from the cache."""
        if self.cache:
            self.cache.clear()

    def clear_tag(self, tag: str) -> None:
        """Remove all cache entries with the specified tag.

        Args:
            tag (str): The tag identifying entries to remove from the cache
        """
        logging.info(f"clearing the sample cache for tag: {tag}")
        removed_vals = self.cache.evict(tag)
        logging.info(f"removed: {removed_vals} items from the cache")

    def close(self) -> None:
        """Close the cache and shutdown the executor if they exist."""
        if self.cache:
            self.cache.close()
        if self.executor:
            self.executor.shutdown()
            self.executor = None

    def stats(self) -> str:
        """Get statistics about cache usage.

        Returns:
            str: A string with cache size information
        """
        logging.info(f"job calls: {self.worker_wrapper_call_count}")
        logging.info(f"cache calls: {self.worker_cache_call_count}")
        logging.info(f"worker calls: {self.worker_fn_call_count}")
        if self.cache:
            return f"cache size :{int(self.cache.volume() / 1000000)}MB / {int(self.size_limit / 1000000)}MB"
        return ""


class JobFunctionCache(FutureCache):
    """A specialized cache for a specific function with various input parameters.

    This class simplifies caching results for a specific function called with
    different sets of parameters. It wraps the general FutureCache with a focus
    on a single function.

    Attributes:
        function (Callable): The function to cache results for
    """

    def __init__(
        self,
        function: Callable,
        overwrite: bool = False,
        executor: Executors = Executors.SERIAL,
        cache_name: str = "fcache",
        tag_index: bool = True,
        size_limit: int = int(100e8),
    ):
        """Initialize a JobFunctionCache for a specific function.

        Args:
            function (Callable): The function to cache results for
            overwrite (bool, optional): Whether to overwrite existing cached results. Defaults to False.
            executor (Executors, optional): The execution strategy to use. Defaults to Executors.SERIAL.
            cache_name (str, optional): Base name for the cache directory. Defaults to "fcache".
            tag_index (bool, optional): Whether to enable tag-based indexing in the cache. Defaults to True.
            size_limit (int, optional): Maximum size of the cache in bytes. Defaults to 10GB.
        """
        super().__init__(
            executor=executor,
            cache_name=cache_name,
            tag_index=tag_index,
            size_limit=size_limit,
            overwrite=overwrite,
        )
        self.function = function

    def call(self, **kwargs) -> JobFuture:
        """Call the wrapped function with the provided arguments.

        This method creates a Job for the function call and submits it through the cache.

        Args:
            **kwargs: Arguments to pass to the function

        Returns:
            JobFuture: A future representing the function call
        """
        return self.submit(Job(self.call_count, self.function, kwargs))
