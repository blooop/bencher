"""Sweep execution for benchmarking.

This module provides the SweepExecutor class for managing parameter sweep execution,
job creation, and cache management in benchmark runs.
"""

import logging
from copy import deepcopy
from typing import Any, Callable, List, Optional, Tuple

import param

from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.job import FutureCache
from bencher.variables.parametrised_sweep import ParametrizedSweep

# Default cache size for benchmark results (100 GB)
DEFAULT_CACHE_SIZE_BYTES = int(100e9)

logger = logging.getLogger(__name__)


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


class SweepExecutor:
    """Manages parameter sweep execution, job creation, and caching.

    This class handles the conversion of variables to parameters, initialization
    of sample caches, and management of cache entries.

    Attributes:
        cache_size (int): Maximum size of the cache in bytes
        sample_cache (FutureCache): Cache for storing sample results
    """

    def __init__(self, cache_size: int = DEFAULT_CACHE_SIZE_BYTES) -> None:
        """Initialize a new SweepExecutor.

        Args:
            cache_size (int): Maximum cache size in bytes. Defaults to 100 GB.
        """
        self.cache_size = cache_size
        self.sample_cache: Optional[FutureCache] = None

    def convert_vars_to_params(
        self,
        variable: param.Parameter | str | dict | tuple,
        var_type: str,
        run_cfg: Optional[BenchRunCfg],
        worker_class_instance: Optional[ParametrizedSweep] = None,
        worker_input_cfg: Optional[ParametrizedSweep] = None,
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
            worker_class_instance (Optional[ParametrizedSweep]): The worker class instance for
                looking up parameters by name
            worker_input_cfg (Optional[ParametrizedSweep]): The worker input configuration class

        Returns:
            param.Parameter: The converted parameter object

        Raises:
            TypeError: If the variable cannot be converted to a param.Parameter
        """
        if isinstance(variable, (str, dict)):
            if worker_class_instance is None:
                raise TypeError(
                    f"Cannot convert {var_type}_vars from string/dict without a worker class instance. "
                    f"Use param.Parameter objects directly or provide a ParametrizedSweep worker."
                )
        if isinstance(variable, str):
            variable = worker_class_instance.param.objects(instance=False)[variable]
        if isinstance(variable, dict):
            param_var = worker_class_instance.param.objects(instance=False)[variable["name"]]
            if variable.get("values"):
                param_var = param_var.with_sample_values(variable["values"])

            if variable.get("samples"):
                param_var = param_var.with_samples(variable["samples"])
            if variable.get("max_level"):
                if run_cfg is not None:
                    param_var = param_var.with_level(run_cfg.execution.level, variable["max_level"])
            variable = param_var
        if not isinstance(variable, param.Parameter):
            raise TypeError(
                f"You need to use {var_type}_vars =[{worker_input_cfg}.param.your_variable], "
                f"instead of {var_type}_vars =[{worker_input_cfg}.your_variable]"
            )
        return variable

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
            const_vars_list, constant_values = [
                [i for i, j in const_vars],
                [j for i, j in const_vars],
            ]

            constant_names = [i.name for i in const_vars_list]
            constant_inputs = dict(zip(constant_names, constant_values))
        return constant_inputs

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
        self.sample_cache = FutureCache(
            overwrite=run_cfg.cache.overwrite_sample_cache,
            executor=run_cfg.execution.executor,
            cache_name="sample_cache",
            tag_index=True,
            size_limit=self.cache_size,
            cache_results=run_cfg.cache.cache_samples,
        )
        return self.sample_cache

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

    def clear_call_counts(self) -> None:
        """Clear the worker and cache call counts.

        This helps debug and assert caching is happening properly.
        """
        if self.sample_cache is not None:
            self.sample_cache.clear_call_counts()

    def close_cache(self) -> None:
        """Close the sample cache if it exists."""
        if self.sample_cache is not None:
            self.sample_cache.close()

    def get_cache_stats(self) -> str:
        """Get statistics about cache usage.

        Returns:
            str: A string with cache statistics
        """
        if self.sample_cache is not None:
            return self.sample_cache.stats()
        return ""
