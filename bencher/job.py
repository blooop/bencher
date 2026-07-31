from __future__ import annotations

import logging
import traceback
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from enum import auto
from typing import Protocol, assert_never, runtime_checkable

from diskcache import Cache
from strenum import StrEnum

from .utils import hash_sha1

logger = logging.getLogger(__name__)

try:
    # scoop is an optional extra and is not in the default environment; the
    # except-ImportError below is the intended handling.
    from scoop import futures as scoop_future_executor  # ty: ignore[unresolved-import]
except ImportError as e:
    scoop_future_executor = None


_MISSING = object()  # Sentinel for cache.get() miss detection


@runtime_checkable
class SupportsSubmit(Protocol):
    """The executor surface bencher actually uses.

    ``Executors.factory`` was annotated ``-> Future | None``, which is the one thing
    it never returns: a ``Future`` is what ``submit()`` *hands back*. The concrete
    values are a ``ProcessPoolExecutor`` and -- for SCOOP -- a *module*, which is why
    naming ``concurrent.futures.Executor`` would be a second, smaller lie. Two
    methods is the whole contract, so a Protocol is both the honest type and the
    narrow one (plan 23 P2).
    """

    def submit(self, fn: Callable, /, *args, **kwargs) -> Future: ...

    def shutdown(self, wait: bool = True) -> None: ...


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
        self,
        job_id: str,
        function: Callable,
        job_args: dict,
        job_key: str | None = None,
        tag: str = "",
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


def normalize_catch(catch) -> tuple[type[BaseException], ...]:
    """Coerce a ``catch=`` value to a tuple of exception types, or reject it.

    Validated eagerly, at the start of the run: left alone, a bare class reaches
    ``tuple(...)`` as ``TypeError: 'type' object is not iterable`` and a string
    becomes a tuple of characters (``catching classes that do not inherit from
    BaseException``), both raised from inside the sampling loop with nothing in the
    message naming ``catch``. A bare exception class is accepted and wrapped,
    because ``catch=RuntimeError`` is the obvious thing to type and there is
    nothing else it could mean.
    """
    if catch is None:
        return ()
    if isinstance(catch, type):  # catch=RuntimeError -- wrap rather than reject
        catch = (catch,)
    # TypeError rather than ValueError because that is what `except` itself raises
    # for a non-exception class -- same failure, reported earlier and by name.
    if isinstance(catch, str) or not isinstance(catch, Iterable):
        raise TypeError(
            f"catch must be an exception type or a tuple of exception types, got {catch!r}"
        )
    catch = tuple(catch)
    for entry in catch:
        if not (isinstance(entry, type) and issubclass(entry, BaseException)):
            raise TypeError(
                f"catch must contain exception types (subclasses of BaseException); got {entry!r}"
            )
    return catch


class WorkerContractError(TypeError):
    """A worker broke the harness contract (returned ``None``, or set a
    ``ResultVec`` to the wrong shape).

    Distinct from a sample fault: the collector records the sample as failed,
    emits :class:`WorkerContractWarning`, surfaces it in the report, and the
    sweep **continues** — a broken sample must never abort a run and lose the
    expensive samples already collected (owner decision amending plan 23 §6.2,
    2026-07-31). Subclasses ``TypeError`` so callers that consumed the previous
    raising behavior still match."""


class WorkerContractWarning(UserWarning):
    """Emitted when a sample is dropped because the worker broke the harness
    contract (see :class:`WorkerContractError`).

    The sample is counted in ``BenchResult.n_failed`` and listed in the
    report's failed-samples summary. Promote to an error in strict pipelines
    with ``warnings.filterwarnings("error", category=bn.WorkerContractWarning)``."""


class WorkerReturnedNothingError(WorkerContractError):
    """A job yielded no result at all -- **the harness's own diagnosis**, never a
    worker's.

    Exists to keep "the framework decided a job produced nothing" separable from
    "a worker raised ``WorkerContractError`` itself", which it can: the class is
    public API (``bencher.WorkerContractError``). ``store_results`` catches *this*
    subclass ahead of ``except catch``, so a framework-minted no-result is always
    recorded-and-continued, while a worker-raised ``WorkerContractError`` keeps
    reaching ``catch=`` exactly as it did before P5.

    Without the split, P5's move of the handler inside the ``try`` silently
    tolerated a worker-raised ``WorkerContractError`` on the pooled path even with
    ``catch=()`` -- loud on SERIAL, silent on MULTIPROCESSING, which is the very
    executor-dependent divergence B3 exists to kill (review finding, 2026-07-31)."""


def _returned_none_error(job_id: str) -> WorkerReturnedNothingError:
    """The contract error for a worker whose call returned ``None``.

    Minted only where that cause is actually *known*: ``require_worker_result``
    (the pooled path, holding the worker's return value) and ``FutureCache.submit``
    at the serial site (which has just called ``run_job``). Both produce the
    identical message."""
    return WorkerReturnedNothingError(
        f"The benchmark function for job {job_id} returned None. "
        "Make sure you are returning a dict or `super().__call__(**kwargs)` "
        "from your __call__ function."
    )


def _no_result_error(job_id: str) -> WorkerReturnedNothingError:
    """The contract error for a ``JobFuture`` built with neither result nor future.

    Deliberately does **not** blame the benchmark function: unlike
    :func:`_returned_none_error` this path does not know the cause. It is reached
    by a cache entry holding ``None`` and by a ``JobFuture`` constructed with no
    arguments at all, both of which the pre-review wording mislabelled as a
    worker bug."""
    return WorkerReturnedNothingError(
        f"No result was produced for job {job_id}: it was constructed with neither "
        "a result nor a pending future. Either a cache entry holds None, or the "
        "JobFuture was built without one of `res=` / `future=` / `error=`."
    )


def require_worker_result(result: dict | None, job_id: str) -> dict:
    """Reject a worker that returned ``None`` instead of a result dict.

    B3 (plan 23 P2): this used to be a bare ``assert`` in ``JobFuture.__init__``,
    which fired only on the serial path -- and not at all under ``python -O``. On
    MULTIPROCESSING/SCOOP the future was set, ``result()`` returned ``None``, and
    ``store_results`` skipped its whole body behind ``if result is not None:`` with
    no ``else``, so the sweep completed green with an all-sentinel dataset and
    ``n_failed == 0``. The same user error was loud or silent depending on an
    unrelated config knob; this is the one check both paths funnel through --
    since P5 it is applied *inside* ``JobFuture.result()``, so a ``None`` can no
    longer leak past the resolve at all.

    Deliberately **not** routed through ``catch=`` (plan 23 decision 2): a missing
    return value is a harness-contract error, not a sample fault, so ``catch=``
    must never decide its fate. That exemption is why the error is the narrow
    :class:`WorkerReturnedNothingError` rather than its public base class -- it must
    apply to the harness's own diagnosis only, never to a ``WorkerContractError`` a
    worker raises. The raise is consumed by ``store_results``, which records the
    sample as failed and warns instead of aborting the sweep (plan 23 §6.2 as
    amended: crashing mid-run loses expensive data; the failure surfaces in the
    report instead)."""
    if result is None:
        raise _returned_none_error(job_id)
    return result


@dataclass(frozen=True)
class SampleFailure:
    """One sample that raised and was tolerated because of ``catch=``.

    Kept as a value on the result so a tolerated failure is *countable*: a run
    that swallowed every sample must not look like a clean run, which is why
    ``fail_on_sample_error`` exists alongside ``catch``.
    """

    job_id: str
    inputs: dict
    exception: str
    traceback: str

    @classmethod
    def from_exception(cls, job_id: str, inputs: dict, exc: BaseException) -> SampleFailure:
        return cls(
            job_id=job_id,
            inputs=dict(inputs),
            exception=repr(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )


@dataclass(frozen=True)
class Ready:
    """A result already in hand: a cache hit, or a serial worker that returned one."""

    res: dict


@dataclass(frozen=True)
class Pending:
    """A submitted job whose result has not been collected from its executor yet."""

    future: Future


@dataclass(frozen=True)
class Broken:
    """A job that yielded no result, carrying the harness's diagnosis of why.

    The error is *stored*, not raised, because the serial path constructs the
    ``JobFuture`` inside the caller's ``except catch`` block -- raising there would
    let ``catch=`` absorb a contract violation (the original B3 failure mode).
    ``result()`` raises it at the consume point instead, where ``store_results``
    records the sample as failed, warns, and continues (plan 23 §6.2 as amended:
    a broken sample must never abort the sweep and lose collected data).

    The error is supplied by whoever *knows* the cause -- ``FutureCache.submit``
    at the serial site, having just seen ``run_job`` return ``None`` -- rather
    than inferred from the syntactic shape of the constructor call, which cannot
    tell a ``None``-returning worker from a cache entry holding ``None``."""

    error: WorkerReturnedNothingError


# The three states a submitted job can be in (plan 23 P5, C2). Previously JobFuture
# held res/future as two optionals and mutated res on the first result() call, so
# both-set and neither-set were representable and `future is not None` stopped meaning
# "pending". Broken is the constructive replacement for the meaningful half of
# "neither-set": the one production path that reached it was a serial worker returning
# None. (A comment rather than a docstring: check-docstring-first reads a bare string
# after a module-level assignment as a misplaced module docstring.)
JobState = Ready | Pending | Broken


class JobFuture:
    """A wrapper for a job result or future that handles caching.

    This class provides a unified interface for handling both immediate results
    and futures (for asynchronous execution). It also handles caching results
    when they become available.

    Attributes:
        job (Job): The job this future corresponds to
        state (JobState): ``Ready(res)`` | ``Pending(future)`` | ``Broken(error)``
        cache: The cache to store results in when they become available
    """

    def __init__(
        self,
        job: Job,
        res: dict | None = None,
        future: Future | None = None,
        cache: Cache | None = None,
        error: WorkerReturnedNothingError | None = None,
    ) -> None:
        """Initialize a JobFuture with a result, a pending future, or an error.

        The keyword signature is kept from the two-optional era so every
        construction site in ``FutureCache.submit`` (and tests that build one
        directly) reads unchanged; the arguments are parsed into a single
        :data:`JobState` here, at the
        boundary. One argument at most may be given -- previously ``res`` and
        ``future`` together were representable and never meaningful. ``error=``
        exists so a caller that *knows* why a job produced nothing (the serial
        site in ``FutureCache.submit``, which has just seen ``run_job`` return
        ``None``) can say so; with none of the three, the state is still
        :class:`Broken`, but with a diagnosis that does not guess at the cause.

        Args:
            job (Job): The job this future corresponds to
            res (dict, optional): The immediate result, if available. Defaults to None.
            future (Future, optional): The future representing the pending result. Defaults to None.
            cache (Cache, optional): The cache to store results in. Defaults to None.
            error (WorkerReturnedNothingError, optional): Why this job produced no
                result, when the caller knows. Defaults to None.
        """
        self.job = job
        # `is not None`, not truthiness: `res={}` is a *valid* result (a worker with
        # no result vars) and must still count as "given" for this check.
        given = [
            name
            for name, val in (("res", res), ("future", future), ("error", error))
            if val is not None
        ]
        if len(given) > 1:
            raise ValueError(
                f"JobFuture for job {job.job_id} was given {' and '.join(given)}; a job is "
                "resolved, still pending, or broken -- never more than one of the three"
            )
        if res is not None:
            self.state: JobState = Ready(res)
        elif future is not None:
            self.state = Pending(future)
        elif error is not None:
            self.state = Broken(error)
        else:
            self.state = Broken(_no_result_error(job.job_id))
        self.cache = cache

    def result(self) -> dict:
        """Get the job result, waiting for completion if necessary.

        If the result is not immediately available (i.e., it's ``Pending``),
        this method will wait for the future to complete. Once the result is
        available, it will be cached if a cache is provided; a worker that
        returned nothing is never cached (the pre-P5 ``res is not None`` guard,
        now enforced by construction).

        Total over :data:`JobState` (plan 23 P5): the pre-P5 ``dict | None``
        return is gone. A worker that returned nothing surfaces as a
        :class:`WorkerReturnedNothingError` raised here -- on *either* executor
        path -- and is consumed by ``store_results``, which records the failure
        and continues rather than aborting the sweep (plan 23 §6.2 as amended).

        Returns:
            dict: The job result

        Raises:
            WorkerReturnedNothingError: If the job produced no result (`Broken`,
                or a `Pending` future that resolves to ``None``). Note this is
                the *narrow* subclass: a ``WorkerContractError`` a worker raises
                itself propagates untouched, and ``store_results`` routes it
                through ``catch=`` like any other sample fault.
        """
        match self.state:
            case Ready(res=res):
                return self._cache_and_return(res)
            case Pending(future=future):
                return self._cache_and_return(
                    require_worker_result(future.result(), self.job.job_id)
                )
            case Broken(error=error):
                raise error
            case _ as unreachable:
                assert_never(unreachable)

    def _cache_and_return(self, res: dict) -> dict:
        """Cache a resolved (never-``None``) result and hand it back."""
        if self.cache is not None:
            self.cache.set(self.job.job_key, res, tag=self.job.tag)
        return res


def run_job(job: Job) -> dict:
    """Execute a job by calling its function with the provided arguments.

    Sets the ``_current_job_key`` context variable so that ``gen_path()``
    places media files into a per-job-key directory for clean lifecycle
    management.

    Args:
        job (Job): The job to execute

    Returns:
        dict: The result of the job execution
    """
    from bencher.utils import _current_job_key, _gen_path_counter

    # Set context *inside* run_job (not in the caller) so it works with
    # ProcessPoolExecutor — child processes start with a fresh ContextVar.
    token = _current_job_key.set(job.job_key)
    counter_token = _gen_path_counter.set({})
    try:
        result = job.function(**job.job_args)
    finally:
        _gen_path_counter.reset(counter_token)
        _current_job_key.reset(token)
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
    def factory(provider: Executors | str) -> SupportsSubmit | None:
        """Create an executor instance based on the specified execution strategy.

        Args:
            provider (Executors | str): The type of executor to create. A raw string
                is normalized to a member first, so the comparisons below can be
                identity checks -- see ``normalize_executor``.

        Returns:
            SupportsSubmit | None: The executor, or None for serial execution

        Raises:
            ValueError: If ``provider`` is not an ``Executors`` member or its value
        """
        # Parse first, so the match below is over a value whose type is established
        # rather than over a raw string (plan 24 A1/A2). Before C13 this compared with
        # `==`, which quietly accepted `"SERIAL"` while FutureCache.submit's `is not`
        # on the same field rejected it.
        match normalize_executor(provider):
            case Executors.SERIAL:
                return None
            case Executors.MULTIPROCESSING:
                try:
                    return ProcessPoolExecutor()
                except (OSError, PermissionError) as exc:  # pragma: no cover - env specific
                    logger.warning(
                        "Falling back to serial execution; multiprocessing unavailable: %s", exc
                    )
                    return None
            case Executors.SCOOP:
                return scoop_future_executor
            case _ as unreachable:
                assert_never(unreachable)


def normalize_executor(executor: Executors | str) -> Executors:
    """Coerce ``executor`` to an ``Executors`` member.

    C13 (plan 23 P2). ``Executors`` is a ``StrEnum``, so ``"SERIAL" ==
    Executors.SERIAL`` is True and ``param.Selector(objects=list(Executors))``
    (``BenchRunCfg.executor``) therefore *accepts* the bare string and stores a
    ``str`` in a field that is compared three different ways: ``==``/``!=`` in
    ``Bench._sample_and_store`` and ``is not`` in ``FutureCache.submit``. An identity
    check against a raw string is False, so those sites disagree the moment one is
    reached with an un-normalized value. Today they still all land on the serial path,
    but only because ``factory`` used to compare with ``==`` as well -- that is luck,
    not design, and it is why plan 23 records C13 as a latent smell rather than a
    shipped bug.

    Normalizing at each ingress is what makes the field's declared type true. Per plan
    24 A2 that is not merely hardening: it is the precondition that licenses matching
    on ``executor`` exhaustively at all, because ``ty`` cannot establish the type of a
    ``param`` descriptor read, and an ``assert_never`` reached with a raw string reads
    as a proof while behaving as an assertion.

    Raises:
        ValueError: for a value outside the vocabulary. ``param.Selector`` rejects
            those on assignment already, so this fires for hand-built configs and
            direct calls -- i.e. at the parse, never at a match site.
    """
    if isinstance(executor, Executors):
        return executor
    try:
        return Executors(executor)
    except ValueError:
        raise ValueError(
            f"executor must be one of {[e.value for e in Executors]} "
            f"(or the matching Executors member), got {executor!r}"
        ) from None


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
        call_count (int): Number of ``JobFunctionCache.call()`` invocations, used to
            label their job ids. Only that subclass increments it; the counters below
            are what a ``FutureCache`` used directly tracks.
        size_limit (int): Maximum size of the cache in bytes
        worker_wrapper_call_count (int): Number of job submissions
        worker_fn_call_count (int): Number of actual function executions
        worker_cache_call_count (int): Number of cache hits
    """

    def __init__(
        self,
        executor: Executors | str = Executors.SERIAL,
        overwrite: bool = True,
        cache_name: str = "fcache",
        tag_index: bool = True,
        size_limit: int = int(20e9),  # 20 GB standalone default; overridden by SweepExecutor
        cache_samples: bool = True,  # internal default; public APIs default to False/None
    ):
        """Initialize a FutureCache with optional caching and execution settings.

        Args:
            executor (Executors, optional): The execution strategy to use. Defaults to Executors.SERIAL.
            overwrite (bool, optional): Whether to overwrite existing cached results. Defaults to True.
            cache_name (str, optional): Base name for the cache directory. Defaults to "fcache".
            tag_index (bool, optional): Whether to enable tag-based indexing in the cache. Defaults to True.
            size_limit (int, optional): Maximum size of the cache in bytes. Defaults to 20GB.
            cache_samples (bool, optional): Whether to cache results at all. Defaults to True.
        """
        # Normalized here as well as in plot_sweep, because FutureCache is also
        # constructed directly (SampleCache, and by callers building their own
        # cache), and `submit()` below discriminates with `is not` (C13).
        self.executor_type = normalize_executor(executor)
        self.executor = None
        if cache_samples:
            self.cache = Cache(f"cachedir/{cache_name}", tag_index=tag_index, size_limit=size_limit)
            logger.info(f"cache dir: {self.cache.directory}")
        else:
            self.cache = None

        self.overwrite = overwrite
        self.call_count = 0
        self.size_limit = size_limit

        self.worker_wrapper_call_count = 0
        self.worker_fn_call_count = 0
        self.worker_cache_call_count = 0

    def prefetch(self, keys: list[str]) -> dict:
        """Pre-load cached values for a batch of keys in one pass.

        Returns a dict mapping key -> cached value for all cache hits.
        This avoids per-job cache round-trips in the submit loop.
        """
        if self.cache is None or self.overwrite:
            return {}
        results = {}
        for key in keys:
            val = self.cache.get(key, _MISSING)
            if val is not _MISSING:
                results[key] = val
        return results

    def submit(self, job: Job, prefetched: dict | None = None) -> JobFuture:
        """Submit a job for execution, with caching if enabled.

        This method first checks the prefetched dict (if provided), then falls back to
        a single cache.get() query. If not found, it executes the job either serially
        or using the configured executor.

        Args:
            job (Job): The job to submit
            prefetched (dict, optional): Pre-fetched cache results from prefetch().
                Defaults to None.

        Returns:
            JobFuture: A future representing the job execution
        """
        self.worker_wrapper_call_count += 1

        if prefetched is not None and job.job_key in prefetched:
            logger.info(f"Found job: {job.job_id} in cache (prefetched)")
            self.worker_cache_call_count += 1
            return JobFuture(job=job, res=prefetched[job.job_key])

        if self.cache is not None and not self.overwrite:
            cached = self.cache.get(job.job_key, _MISSING)
            if cached is not _MISSING:
                logger.info(f"Found job: {job.job_id} in cache, loading...")
                self.worker_cache_call_count += 1
                return JobFuture(job=job, res=cached)

        self.worker_fn_call_count += 1

        # Clean up stale media from the previous run *before* executing,
        # so the new run can write fresh files into the same job-key dir.
        if self.cache is not None and job.job_key in self.cache:
            from bencher.cache_management import cleanup_job_media

            try:
                cleanup_job_media(job.job_key)
            except OSError as exc:
                logger.warning("Failed to clean up media for job %s: %s", job.job_key, exc)

        if self.executor_type is not Executors.SERIAL and self.executor is None:
            self.executor = Executors.factory(self.executor_type)
        if self.executor is not None:
            self.overwrite_msg(job, " starting parallel job...")
            return JobFuture(
                job=job,
                future=self.executor.submit(run_job, job),
                cache=self.cache,
            )
        self.overwrite_msg(job, " starting serial job...")
        # The one place that can distinguish "the worker returned None" from any
        # other route to a result-less job, so it is the place that names the cause
        # (review finding 4). Passing `res=None` and letting the constructor guess
        # would relabel a cached None as a benchmark-function bug.
        res = run_job(job)
        if res is None:
            return JobFuture(job=job, error=_returned_none_error(job.job_id), cache=self.cache)
        return JobFuture(
            job=job,
            res=res,
            cache=self.cache,
        )

    def overwrite_msg(self, job: Job, suffix: str) -> None:
        """Log a message about overwriting or using cache.

        Args:
            job (Job): The job being executed
            suffix (str): Additional text to add to the log message
        """
        msg = "OVERWRITING" if self.overwrite else "NOT in"
        logger.info(f"{job.job_id} {msg} cache{suffix}")

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

        Note: diskcache.evict() does not return the evicted values, so media
        files referenced by evicted entries may become orphans.  Use
        ``clean_orphaned_media()`` periodically to reclaim them.

        Args:
            tag (str): The tag identifying entries to remove from the cache
        """
        # Guarded like every other cache access here: with cache_samples=False this
        # used to be a live AttributeError on None (found by the strict ty ratchet,
        # plan 23 P2 item 7; fixed in P5 when this file joined the strict list).
        # WARNING rather than a silent return: the public entry point
        # (Bench.clear_tag_from_sample_cache) is reachable from user code, and
        # "nothing happened" must not look like "the tag was cleared".
        if self.cache is None:
            logger.warning(
                "asked to clear tag %r from a sample cache that does not exist "
                "(cache_samples=False); nothing to clear",
                tag,
            )
            return
        logger.info(f"clearing the sample cache for tag: {tag}")
        removed_vals = self.cache.evict(tag)
        logger.info(f"removed: {removed_vals} items from the cache")

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
        logger.info(f"job calls: {self.worker_wrapper_call_count}")
        logger.info(f"cache calls: {self.worker_cache_call_count}")
        logger.info(f"worker calls: {self.worker_fn_call_count}")
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
        executor: Executors | str = Executors.SERIAL,
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
        # `call_count` is incremented here, which is what makes the job_id below
        # identify a call. It was initialised to 0 in FutureCache.__init__ and
        # incremented nowhere, so every call produced job_id=0 -- indistinguishable
        # in logs and in every contract-violation message. The strict ty ratchet
        # flagged only the type (int passed as a str job_id); casting alone would
        # have made the annotation true while preserving the defect it pointed at
        # (review finding 2).
        self.call_count += 1
        return self.submit(Job(f"call {self.call_count}", self.function, kwargs))
