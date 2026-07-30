"""Result collection and storage for benchmarking.

This module provides the ResultCollector class for managing benchmark results,
including xarray dataset operations, caching, and metadata management.
"""

from __future__ import annotations

import logging
import math
import os
from contextlib import suppress
from datetime import datetime
from itertools import product
from typing import Any

import numpy as np
import xarray as xr
from diskcache import Cache

from bencher.bench_cfg import BenchCfg, BenchRunCfg, DimsCfg
from bencher.cache_management import DEFAULT_CACHE_SIZE_BYTES
from bencher.history import (
    HISTORY_FORMAT,
    HistoryEvent,
    apply_policy,
    column_meta,
    current_time_value,
    data_var_columns,
    default_series_id,
    diff_summaries,
    incompatible_reason,
    last_seen_key,
    legacy_last_seen_key,
    project,
    reconcile,
)
from bencher.job import JobFuture, SampleFailure, normalize_catch
from bencher.results.bench_result import BenchResult
from bencher.variables.inputs import IntSweep
from bencher.variables.results import (
    DATA_VAR_RESULT_TYPES,
    XARRAY_MULTIDIM_RESULT_TYPES,
    ResultContainer,
    ResultDataSet,
    ResultFloat,
    ResultImage,
    ResultPath,
    ResultReference,
    ResultRerun,
    ResultVec,
    ResultVideo,
    result_missing_fill,
)
from bencher.variables.time import TimeEvent, TimeSnapshot
from bencher.worker_job import WorkerJob

logger = logging.getLogger(__name__)

_MEDIA_RESULT_TYPES = (ResultPath, ResultVideo, ResultImage, ResultContainer, ResultRerun)


def _sentinel_for_result_var(rv):
    """Return the sentinel value used for 'missing' entries of this result type.

    Thin wrapper over the single source of truth in ``bencher.variables.results``
    (``result_missing_fill``); kept as a local alias for the over_time aging path.
    """
    return result_missing_fill(rv)[0]


def _null_old_entries(dataset, rv, var_limit):
    """Null out over_time entries older than *var_limit* for a single result variable.

    **Mutates *dataset* in-place** by writing sentinel values directly into
    the backing numpy arrays of the affected data variables.

    For media types (images, videos, .rrd files), the referenced files are
    collected for deferred deletion.  Returns a list of file paths to delete;
    the caller is responsible for removing them *after* the dataset is cached
    so that a cache-write failure does not leave orphaned sentinel values.
    """
    n_time = dataset.sizes["over_time"]
    if var_limit is None or var_limit >= n_time:
        return []

    null_count = n_time - var_limit
    sentinel = _sentinel_for_result_var(rv)
    is_media = isinstance(rv, _MEDIA_RESULT_TYPES)
    files_to_delete = []

    if isinstance(rv, ResultVec):
        var_names = rv.index_names()
    else:
        var_names = [rv.name]

    for vname in var_names:
        if vname not in dataset:
            continue
        da = dataset[vname]
        # over_time is always the last axis (dims = input_vars + [repeat, over_time])
        for t_idx in range(null_count):
            if is_media:
                old_slice = da.isel(over_time=t_idx).values
                for val in np.asarray(old_slice).flat:
                    if val != sentinel and isinstance(val, str) and os.path.isfile(val):
                        files_to_delete.append(val)
            da.values[..., t_idx] = sentinel

    return files_to_delete


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
    bench_res: BenchResult,
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


def _materialize_result_value(rv, value):
    """Convert deferred result artifacts into their cacheable stored representation."""
    if isinstance(rv, ResultRerun):
        from bencher.results.composable_container.composable_container_rerun import (
            ComposableContainerRerun,
        )

        if isinstance(value, ComposableContainerRerun):
            return value.render()
    return value


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

    # typing.Self needs python 3.11 and the package floor is 3.10, so keep the
    # concrete return type rather than take a typing_extensions dependency.
    def __enter__(self) -> ResultCollector:  # noqa: PYI034
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
            if type(rv) is ResultVec:
                # ResultVec expands to one column per vector element.
                fill, dtype = result_missing_fill(rv)
                for i in range(rv.size):
                    result_data = np.full(dims_cfg.dims_size, fill, dtype=dtype)
                    data_vars[rv.index_name(i)] = (dims_cfg.dims_name, result_data)
            elif isinstance(rv, DATA_VAR_RESULT_TYPES):
                fill, dtype = result_missing_fill(rv)
                result_data = np.full(dims_cfg.dims_size, fill, dtype=dtype)
                data_vars[rv.name] = (dims_cfg.dims_name, result_data)

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

    @staticmethod
    def record_caught_sample(
        bench_res: BenchResult, job_id: str, inputs: dict, exc: BaseException
    ) -> None:
        """Record one tolerated sample failure.

        No write to the dataset is needed: ``setup_dataset`` already filled every
        result variable with its missing-value sentinel, so the failed coordinate
        *is* the fill and the dataset shape is unchanged -- downstream consumers
        need no special case. Nothing was written to the sample cache either,
        because the exception escaped before the cache write in both execution
        paths, so a transient flake cannot become a permanent cached failure.
        """
        failure = SampleFailure.from_exception(job_id, inputs, exc)
        bench_res.failed_samples.append(failure)
        logger.warning(
            "sample failed and was caught (%s): %s",
            ", ".join(f"{k}={v}" for k, v in failure.inputs.items()) or "no inputs",
            failure.exception,
        )

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
        # No `if catch:` branch: `except ()` matches nothing, so the default empty
        # tuple is already fail-fast, and result() keeps a single call site.
        # Normalized here as well as in plot_sweep, because store_results is also
        # reachable with a hand-built BenchRunCfg that never passed through it.
        catch = normalize_catch(getattr(bench_run_cfg, "catch", ()))
        try:
            result = job_result.result()
        # catch is a runtime tuple of exception types, which pylint cannot see into.
        # pylint: disable-next=catching-non-exception
        except catch as exc:
            self.record_caught_sample(
                bench_res, job_result.job.job_id, worker_job.function_input, exc
            )
            return
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
                result_value = _materialize_result_value(rv, result_value)
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
                    if (
                        isinstance(result_value, (list, np.ndarray))
                        and len(result_value) == rv.size
                    ):
                        for i in range(rv.size):
                            _set_result_value(
                                bench_res, rv_arrays, rv.index_name(i), idx, result_value[i]
                            )

                else:
                    raise TypeError(f"Unsupported result type: {type(rv).__name__}")
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

    def _read_last_seen(
        self, cache: Cache, series_id: str, bench_name: str | None, tag: str | None
    ) -> dict | None:
        """The last-seen index entry for *series_id*, falling back to the legacy key.

        Ordered: the series key first, then the pre-``series_id`` ``(bench_name,
        tag)`` key, so the first run after upgrade finds its predecessor. A legacy
        hit needs no explicit migration -- this run's write lands under the new key
        at the end of ``load_history_cache``. The two keys are the *same string*
        unless a ``series_id`` was declared, so the fallback only does work where it
        has to.
        """
        entry = cache.get(last_seen_key(series_id))
        if entry is not None or bench_name is None:
            return entry
        return cache.get(legacy_last_seen_key(bench_name, tag))

    def _adopt_or_report_reset(
        self,
        cache: Cache,
        bench_cfg_hash: str,
        *,
        series_id: str,
        bench_name: str | None,
        tag: str | None,
        config_summary: dict | None,
        events: list[HistoryEvent],
    ) -> dict | None:
        """Classify a history-key miss under a known series: adopt, or report a reset.

        A key can move for two very different reasons, and until the series was
        named independently of the key there was no way to tell them apart. The
        stored ``config_summary`` decides:

        * **identical** -- the declaration did not change, so only ``bench_name``
          or ``tag`` moved: a pure rename. The stored record is re-keyed to the new
          hash and a non-lossy ``history_renamed`` event is emitted. Safe precisely
          because the summary covers every field that shapes the dataset -- same
          dimensions, same coordinates, same columns -- and the record is *moved*,
          never concatenated with an incompatible one.
        * **differs** -- a genuinely different experiment, which is the existing
          ``full_reset`` with its diff.

        Returns the adopted record, or None to continue as a fresh series.
        """
        last = self._read_last_seen(cache, series_id, bench_name, tag)
        if not last or last.get("key") == bench_cfg_hash:
            return None

        old_key = last.get("key")
        diff = diff_summaries(last.get("summary"), config_summary)
        stored_summary = last.get("summary")
        renamed = (
            stored_summary is not None
            and config_summary is not None
            and stored_summary == config_summary
        )
        if renamed:
            adopted = self._load_history_record(cache, old_key) if old_key else None
            if adopted is not None:
                events.append(
                    HistoryEvent(
                        "history_renamed",
                        f"over_time history adopted for series '{series_id}': the "
                        f"history key moved from {old_key} to {bench_cfg_hash} with an "
                        f"unchanged declaration (benchmark '{bench_name}', tag "
                        f"'{tag}'), so the existing "
                        f"{last.get('events', '?')} events were carried over",
                    )
                )
                with suppress(KeyError, OSError):
                    del cache[old_key]
                return adopted

        detail = (
            f"over_time history reset for benchmark '{bench_name}' "
            f"(tag '{tag}'): the history key changed"
            + (": " + "; ".join(diff) if diff else "")
            + f"; {last.get('events', '?')} historical events are "
            f"orphaned under the old key"
        )
        events.append(HistoryEvent("full_reset", detail))
        return None

    def _load_history_record(self, cache: Cache, bench_cfg_hash: str) -> dict | None:
        """Fetch and normalize one history record, or None when absent/unreadable.

        Bare ``xr.Dataset`` values (hand-seeded or pre-record entries) are
        wrapped into the record shape with no column metadata, which the
        reconciler treats as adopt-in-place.
        """
        try:
            record = cache[bench_cfg_hash]
        except KeyError:
            return None
        except (AttributeError, TypeError, ModuleNotFoundError, ImportError) as exc:
            logger.warning(
                "Failed to deserialize cached history (%s: %s). "
                "Discarding stale cache entry and continuing with fresh data.",
                type(exc).__name__,
                exc,
            )
            try:
                del cache[bench_cfg_hash]
            except (OSError, KeyError) as del_exc:
                logger.debug("Could not remove stale cache entry: %s", del_exc)
            return None
        if isinstance(record, xr.Dataset):
            return {"format": 0, "dataset": record, "columns": {}, "retired": {}}
        if isinstance(record, dict) and isinstance(record.get("dataset"), xr.Dataset):
            return record
        logger.warning("Unrecognized history record shape; discarding stale entry")
        try:
            del cache[bench_cfg_hash]
        except (OSError, KeyError) as del_exc:
            logger.debug("Could not remove stale cache entry: %s", del_exc)
        return None

    def load_history_cache(
        self,
        dataset: xr.Dataset,
        bench_cfg_hash: str,
        clear_history: bool,
        max_time_events: int | None = None,
        result_vars: list | None = None,
        *,
        on_history_reset: str = "warn",
        bench_name: str | None = None,
        tag: str | None = None,
        series_id: str | None = None,
        config_summary: dict | None = None,
    ) -> xr.Dataset:
        """Load, reconcile, and persist historical benchmark data.

        The history key excludes result variables, so the stored record is a
        *superset* of every column ever measured under this benchmark's input
        space; result-var differences are reconciled per column (retained,
        retired, resumed, or born — see :mod:`bencher.history`) and consumers
        receive a projection onto exactly the current ``result_vars`` columns.
        If clear_history is True, existing history is ignored (a fresh series
        starts and is written back).

        Args:
            dataset (xr.Dataset): Freshly calculated benchmark data for the current run
            bench_cfg_hash (str): History key — the benchmark identity hash computed
                with ``include_result_vars=False``
            clear_history (bool): If True, clears historical data instead of loading it
            max_time_events (int | None): Maximum number of over_time events to retain.
                Oldest events are trimmed. None means unlimited.
            result_vars (list | None): Result variable instances defining the served
                columns. Also used for per-variable ``max_time_events`` aging. When
                None, column reconciliation and projection are skipped entirely.
            on_history_reset (str): Policy for loss-y schema events — "warn",
                "error" (raise HistoryResetError before persisting), or "ignore".
            bench_name (str | None): Benchmark name, used in event messages and as
                half of the legacy index key read during the one-release upgrade.
            tag (str | None): Benchmark tag, same two uses as bench_name.
            series_id (str | None): The series this run appends to
                (``BenchCfg.series``). Keys the last-seen index, which is what lets
                a pure rename be adopted rather than silently orphaned. When None
                the series falls back to ``bench_name:tag``, so the index is still
                consulted and reset detection is unchanged for callers that declare
                nothing; the index is skipped only when ``bench_name`` is None too.
            config_summary (dict | None): ``bencher.history.config_summary`` of the
                current config, stored in the last-seen index and diffed on resets.

        Returns:
            xr.Dataset: The current config's view of the accumulated history —
                historical plus current data, projected onto the current columns.
        """
        c = self.get_history_cache()
        # An explicit series_id wins; otherwise the series is bench_name:tag, which
        # is what the index was keyed on before series_id existed. Deriving it here
        # rather than requiring it keeps every existing caller's reset detection.
        series = series_id or (
            default_series_id(bench_name, tag) if bench_name is not None else None
        )
        current_cols = data_var_columns(result_vars)
        events: list[HistoryEvent] = []
        merged = dataset
        birth_val = current_time_value(dataset)
        columns_meta = {name: column_meta(rv, name, birth_val) for name, rv in current_cols.items()}
        retired: dict = {}

        if clear_history:
            logger.info("clearing history")
        else:
            logger.info(f"checking historical key: {bench_cfg_hash}")
            record = self._load_history_record(c, bench_cfg_hash)
            if record is None and series is not None:
                record = self._adopt_or_report_reset(
                    c,
                    bench_cfg_hash,
                    series_id=series,
                    bench_name=bench_name,
                    tag=tag,
                    config_summary=config_summary,
                    events=events,
                )
            if record is None:
                logger.info("did not detect any historical data")
            else:
                logger.info("loading historical data from cache")
                ds_old = record["dataset"]
                incompatible = incompatible_reason(ds_old, dataset)
                if incompatible:
                    events.append(
                        HistoryEvent(
                            "history_discarded",
                            f"Discarding incompatible historical data ({incompatible})",
                        )
                    )
                elif current_cols:
                    merged, columns_meta, retired, reconcile_events = reconcile(
                        record, dataset, current_cols
                    )
                    events.extend(reconcile_events)
                else:
                    # No column information (result_vars not supplied): plain
                    # append, preserving whatever metadata the record carries.
                    merged = xr.concat([ds_old, dataset], "over_time")
                    columns_meta = record.get("columns") or {}
                    retired = record.get("retired") or {}

        # Policy runs before anything is persisted so on_history_reset="error"
        # leaves the stored history untouched for the next (acknowledged) run.
        apply_policy(events, on_history_reset)

        if (
            max_time_events is not None
            and "over_time" in merged.dims
            and merged.sizes["over_time"] > max_time_events
        ):
            merged = merged.isel(over_time=slice(-max_time_events, None))

        # Per-variable max_time_events: null out older entries for variables
        # with a per-variable limit smaller than the dataset's over_time size.
        # File deletion is deferred until after the cache write succeeds.
        pending_deletes = []
        if result_vars and "over_time" in merged.dims:
            for rv in result_vars:
                var_limit = getattr(rv, "max_time_events", None)
                if var_limit is not None:
                    pending_deletes.extend(_null_old_entries(merged, rv, var_limit))

        logger.info("saving data to history cache")
        c[bench_cfg_hash] = {
            "format": HISTORY_FORMAT,
            "dataset": merged,
            "columns": columns_meta,
            "retired": retired,
        }
        if series is not None:
            c[last_seen_key(series)] = {
                "key": bench_cfg_hash,
                "summary": config_summary,
                "events": int(merged.sizes.get("over_time", 0)),
            }

        for fpath in pending_deletes:
            try:
                os.remove(fpath)
                logger.debug("Deleted nulled media file: %s", fpath)
            except OSError as exc:
                logger.warning("Failed to delete media file %s: %s", fpath, exc)

        if current_cols:
            return project(merged, current_cols, columns_meta)
        return merged

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
