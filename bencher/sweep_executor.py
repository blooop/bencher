"""Sweep execution for benchmarking.

This module provides the SweepExecutor class for managing parameter sweep execution,
job creation, and cache management in benchmark runs.
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from copy import deepcopy
from typing import Any

import param

from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.cache_management import DEFAULT_CACHE_SIZE_BYTES
from bencher.job import FutureCache
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.sweep_base import hash_sha1


def _resolve_param(
    name: str,
    worker: ParametrizedSweep,
    var_type: str,
) -> param.Parameter:
    """Look up a param.Parameter by *name* on *worker*, raising a helpful KeyError if missing."""
    all_params = worker.param.objects(instance=False)
    if name not in all_params:
        available = sorted(k for k in all_params if k != "name")
        raise KeyError(
            f"{var_type.capitalize()} variable '{name}' not found on "
            f"{type(worker).__name__}. "
            f"Available parameters: {available}"
        ) from None
    return all_params[name]


def _positions_by_name(names: list[str]) -> dict[str, list[int]]:
    """Declared positions of each name, in declaration order."""
    out: dict[str, list[int]] = {}
    for index, name in enumerate(names):
        out.setdefault(name, []).append(index)
    return out


def validate_declared_vars(
    input_vars: list[param.Parameter],
    result_vars: list[param.Parameter],
    const_vars: list[list],
) -> tuple[list[param.Parameter], list[param.Parameter], list[list]]:
    """Reject or normalise variables declared more than once in one sweep.

    Compares resolved ``name``, so the string, dict and object declaration forms
    are all covered and a mixture of them is too. The three kinds get three
    answers because the data model gives them three meanings, not out of
    leniency:

    * **Input** -- raises. Each input variable is one dataset dimension, and a
      repeated dimension has no valid interpretation; it already fails, deep
      inside xarray's broadcasting with no reference to the declaration.
    * **Result** -- deduped on name, first occurrence kept, ``UserWarning``.
      The deduped set is already what bencher stores: the dataset's ``data_vars``
      and history's per-column metadata are both keyed by name, so a repeat
      collapses there. Only ``BenchCfg.hash_persistent`` disagreed, folding the
      per-variable digests as a sorted *tuple* so a repeat appeared twice and
      moved the key. Deduping makes cache and history identity agree with the
      data that was already being written.
    * **Const** -- deduped when the values agree, raises when they disagree.
      A repeated constant with two different values is a contradiction in the
      declaration, and which one won depended on iteration order.

    Returns:
        The three lists, with duplicate result and const entries removed.

    Raises:
        ValueError: On a duplicate input variable, or a duplicate constant with
            conflicting values.
    """
    for name, positions in _positions_by_name([v.name for v in input_vars]).items():
        if len(positions) > 1:
            raise ValueError(
                f"Input variable '{name}' is declared {len(positions)} times "
                f"(positions {positions}). Each input variable defines one dataset "
                f"dimension, so it may appear only once."
            )

    kept_results: list[param.Parameter] = []
    first_result: dict[str, int] = {}
    for index, var in enumerate(result_vars):
        if var.name in first_result:
            warnings.warn(
                f"Result variable '{var.name}' is declared twice (positions "
                f"{first_result[var.name]} and {index}); the duplicate is ignored. "
                f"Result variables are a set keyed by name -- declare each metric "
                f"once. Until now the repeat moved the cache and history key "
                f"without changing the data.",
                UserWarning,
                stacklevel=3,
            )
            continue
        first_result[var.name] = index
        kept_results.append(var)

    kept_consts: list[list] = []
    first_const: dict[str, tuple[int, Any]] = {}
    for index, entry in enumerate(const_vars):
        var, value = entry[0], entry[1]
        if var.name in first_const:
            prev_index, prev_value = first_const[var.name]
            if hash_sha1(prev_value) != hash_sha1(value):
                raise ValueError(
                    f"Constant '{var.name}' is declared twice with different values: "
                    f"{prev_value!r} at position {prev_index} and {value!r} at "
                    f"position {index}. Which one applied depended on iteration "
                    f"order, so declare it once with the value you mean."
                )
            continue
        first_const[var.name] = (index, value)
        kept_consts.append(entry)

    return input_vars, kept_results, kept_consts


# Metadata keys that must never be forwarded to the worker function.
_META_KEYS = frozenset({"over_time", "time_event"})

logger = logging.getLogger(__name__)


def worker_kwargs_wrapper(worker: Callable, bench_cfg: BenchCfg, **kwargs) -> dict:
    """Prepare keyword arguments and pass them to a worker function.

    This wrapper filters out metadata parameters that should not be passed
    to the worker function (like 'repeat', 'over_time', and 'time_event'),
    then deep-copies the filtered dict for mutation safety before calling
    the worker.

    Args:
        worker (Callable): The worker function to call
        bench_cfg (BenchCfg): Benchmark configuration with parameters like pass_repeat
        **kwargs: The keyword arguments to filter and pass to the worker

    Returns:
        dict: The result from the worker function
    """
    filtered = {
        k: v
        for k, v in kwargs.items()
        if k not in _META_KEYS and (k != "repeat" or bench_cfg.pass_repeat)
    }
    return worker(**deepcopy(filtered))


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
        self.sample_cache: FutureCache | None = None

    def convert_vars_to_params(
        self,
        variable: param.Parameter | str | dict | tuple,
        var_type: str,
        run_cfg: BenchRunCfg | None,
        worker_class_instance: ParametrizedSweep | None = None,
        worker_input_cfg: ParametrizedSweep | None = None,
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
                - dict: Configuration with 'name' and optional 'values', 'samples', 'max_subsampling_divisions'
                - tuple: Tuple that can be converted to a parameter
            var_type (str): Type of variable ('input', 'result', or 'const') for error messages
            run_cfg (BenchRunCfg | None): Run configuration for level settings
            worker_class_instance (ParametrizedSweep | None): The worker class instance for
                looking up parameters by name
            worker_input_cfg (ParametrizedSweep | None): The worker input configuration class

        Returns:
            param.Parameter: The converted parameter object

        Raises:
            TypeError: If the variable cannot be converted to a param.Parameter
        """
        if isinstance(variable, (str, dict)) and worker_class_instance is None:
            raise TypeError(
                f"Cannot convert {var_type}_vars from string/dict without a worker class instance. "
                f"Use param.Parameter objects directly or provide a ParametrizedSweep worker."
            )
        if isinstance(variable, str):
            variable = _resolve_param(variable, worker_class_instance, var_type)
        if isinstance(variable, dict):
            var_name = variable["name"]
            param_var = _resolve_param(var_name, worker_class_instance, var_type)
            if variable.get("values"):
                param_var = param_var.with_sample_values(variable["values"])
            elif variable.get("bounds"):
                b = variable["bounds"]
                param_var = param_var.with_bounds(b[0], b[1], variable.get("samples"))
            elif variable.get("samples"):
                param_var = param_var.with_samples(variable["samples"])
            if variable.get("max_subsampling_divisions") and run_cfg is not None:
                param_var = param_var.with_subsampling_divisions(
                    run_cfg.subsampling_divisions, variable["max_subsampling_divisions"]
                )
            variable = param_var
        if not isinstance(variable, param.Parameter):
            raise TypeError(
                f"You need to use {var_type}_vars =[{worker_input_cfg}.param.your_variable], "
                f"instead of {var_type}_vars =[{worker_input_cfg}.your_variable]"
            )
        return variable

    def define_const_inputs(self, const_vars: list[tuple[param.Parameter, Any]]) -> dict | None:
        """Convert constant variable tuples into a dictionary of name-value pairs.

        Args:
            const_vars (list[tuple[param.Parameter, Any]]): List of (parameter, value) tuples
                representing constant parameters and their values

        Returns:
            dict | None: Dictionary mapping parameter names to their constant values,
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
            overwrite=run_cfg.overwrite_sample_cache,
            executor=run_cfg.executor,
            cache_name="sample_cache",
            tag_index=True,
            size_limit=self.cache_size,
            cache_samples=run_cfg.cache_samples,
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
