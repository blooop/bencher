import logging
import random
import unittest
from concurrent.futures import Future

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import bencher as bn
from bencher.job import (
    Broken,
    FutureCache,
    Job,
    JobFunctionCache,
    JobFuture,
    Pending,
    Ready,
    WorkerContractError,
    WorkerReturnedNothingError,
)


class CachedParamExample(bn.ParametrizedSweep):
    var1 = bn.FloatSweep(default=0, bounds=[0, 10])
    var2 = bn.IntSweep(default=10, bounds=[0, 10])

    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.var1 + self.var2 + random.uniform(0, 1)


class TestJob(unittest.TestCase):
    @settings(deadline=5000)  # Increased deadline for multiprocessing startup overhead
    @given(st.sampled_from([bn.Executors.SERIAL, bn.Executors.MULTIPROCESSING]))
    def test_basic(self, executor):
        cp = CachedParamExample()  # clears cache by default

        jc = JobFunctionCache(cp.__call__, executor=executor, cache_name="test_cache")
        jc.clear_cache()

        res1 = jc.call(var1=1).result()
        res2 = jc.call(var1=1).result()
        res3 = jc.call(var1=2).result()
        res4 = jc.call(var2=2).result()

        # will only be equal if cache is used because of the randomness
        self.assertEqual(res1["result"], res2["result"])
        self.assertNotEqual(res1["result"], res3["result"], f"{res1}")
        self.assertNotEqual(res1["result"], res4["result"], f"{res1}")

        # create new class, make sure it has the same results
        cp2 = CachedParamExample()
        jc2 = JobFunctionCache(cp2.__call__, executor=executor, cache_name="test_cache")
        res1cp2 = jc2.call(var1=1).result()
        self.assertEqual(res1["result"], res1cp2["result"])

        # create cache with a different name and check it does not have the same results
        cp3 = CachedParamExample()
        jc3 = JobFunctionCache(cp3.__call__, executor=executor, cache_name="test_cache2")
        res1cp3 = jc3.call(var1=1).result()
        self.assertNotEqual(res1["result"], res1cp3["result"])

    @settings(deadline=5000)  # Increased deadline for multiprocessing startup overhead
    @given(st.sampled_from([bn.Executors.SERIAL, bn.Executors.MULTIPROCESSING]))
    def test_overwrite(self, executor):
        cp = CachedParamExample()  # clears cache by default

        jc = JobFunctionCache(cp.__call__, executor=executor, cache_name="test_cache1")
        jc.clear_cache()

        res1 = jc.call(var1=1).result()

        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 0)
        self.assertEqual(jc.worker_fn_call_count, 1)

        jc.clear_call_counts()
        res2 = jc.call(var1=1).result()

        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 1)
        self.assertEqual(jc.worker_fn_call_count, 0)

        self.assertEqual(res1["result"], res2["result"])

        jc.clear_call_counts()
        jc.overwrite = True
        res3 = jc.call(var1=1).result()
        self.assertEqual(jc.worker_wrapper_call_count, 1)
        self.assertEqual(jc.worker_cache_call_count, 0)
        self.assertEqual(jc.worker_fn_call_count, 1)

        self.assertNotEqual(res1["result"], res3["result"], f"{res1}")

    @settings(deadline=5000)  # Increased deadline for multiprocessing startup overhead
    @given(st.sampled_from([bn.Executors.SERIAL, bn.Executors.MULTIPROCESSING]))
    def test_bench_runner_parallel(self, executor):
        run_cfg = bn.BenchRunCfg()
        run_cfg.overwrite_sample_cache = True
        run_cfg.executor = executor
        bench_run = bn.BenchRunner("test_bench_runner", run_cfg=run_cfg)

        bench_run.add_bench(CachedParamExample())

        bench_run.run(subsampling_divisions=2)


class _RecordingCache:
    """Minimal stand-in for diskcache.Cache recording only what was written."""

    def __init__(self) -> None:
        self.sets: list[tuple] = []

    def set(self, key, value, tag=None) -> None:
        self.sets.append((key, value, tag))


def _job(job_id: str = "job-1") -> Job:
    return Job(job_id=job_id, function=lambda **_: None, job_args={"x": 1}, tag="t")


class TestJobFutureState:
    """C2 (plan 23 P5): one field holding ``Ready | Pending | Broken``.

    ``res``/``future`` used to be two independent optionals that ``result()``
    *mutated*, so ``future is not None`` stopped meaning "pending" after the
    first call, and both-set / neither-set were both representable.
    """

    def test_a_result_parses_to_ready(self) -> None:
        assert JobFuture(job=_job(), res={"y": 1.0}).state == Ready({"y": 1.0})

    def test_a_future_parses_to_pending(self) -> None:
        future: Future = Future()
        assert JobFuture(job=_job(), future=future).state == Pending(future)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"res": {"y": 1.0}, "future": "future"},
            {"res": {"y": 1.0}, "error": "error"},
            {"future": "future", "error": "error"},
        ],
        ids=["res+future", "res+error", "future+error"],
    )
    def test_more_than_one_variant_at_once_is_rejected(self, kwargs) -> None:
        """Previously representable, never meaningful."""
        placeholders = {
            "future": Future(),
            "error": WorkerReturnedNothingError("boom"),
        }
        kwargs = {k: placeholders.get(v, v) if isinstance(v, str) else v for k, v in kwargs.items()}
        with pytest.raises(ValueError, match="never more than one of the three"):
            JobFuture(job=_job(), **kwargs)

    def test_an_empty_dict_result_still_counts_as_given(self) -> None:
        """`res={}` is falsy but a valid result, so the conflict check must see it."""
        with pytest.raises(ValueError, match="never more than one of the three"):
            JobFuture(job=_job(), res={}, future=Future())

    def test_resolving_does_not_change_the_variant(self) -> None:
        """The order-dependent read `bencher.py` used to do is now stable.

        Pre-P5, ``result()`` assigned to ``self.res`` but left ``self.future``
        set, so the meaning of a state read depended on whether ``result()``
        had already been called.
        """
        future: Future = Future()
        future.set_result({"y": 1.0})
        job_future = JobFuture(job=_job(), future=future)
        assert job_future.result() == {"y": 1.0}
        assert job_future.state == Pending(future)

    def test_a_ready_result_is_cached(self) -> None:
        cache = _RecordingCache()
        JobFuture(job=_job(), res={"y": 1.0}, cache=cache).result()
        assert cache.sets == [(_job().job_key, {"y": 1.0}, "t")]

    def test_a_pending_result_is_cached_on_resolve(self) -> None:
        cache = _RecordingCache()
        future: Future = Future()
        future.set_result({"y": 2.0})
        JobFuture(job=_job(), future=future, cache=cache).result()
        assert cache.sets == [(_job().job_key, {"y": 2.0}, "t")]


class TestJobFutureNoneReturn:
    """B3's disposition, preserved through the new type (plan 23 §6.2 as amended).

    ``result()`` is total -- it no longer returns ``dict | None`` -- so a job that
    produced nothing raises ``WorkerReturnedNothingError`` on *either* executor
    path. ``store_results`` consumes that and records-and-continues; nothing
    here may abort a sweep on its own.
    """

    def test_neither_result_nor_future_is_broken(self) -> None:
        state = JobFuture(job=_job()).state
        assert isinstance(state, Broken)
        assert isinstance(state.error, WorkerReturnedNothingError)

    def test_broken_raises_at_the_consume_point_not_at_construction(self) -> None:
        """Construction must stay quiet: the serial site is inside `except catch`."""
        job_future = JobFuture(job=_job("job-42"))  # no raise here
        with pytest.raises(WorkerReturnedNothingError, match="job-42"):
            job_future.result()

    def test_the_generic_diagnosis_does_not_blame_the_benchmark_function(self) -> None:
        """This path cannot know the cause -- a cached None reaches it too.

        Only ``FutureCache.submit``'s serial site and ``require_worker_result``
        have actually observed a worker return ``None``, so only they say so.
        """
        with pytest.raises(WorkerReturnedNothingError) as exc_info:
            JobFuture(job=_job()).result()
        msg = str(exc_info.value)
        assert "neither a result nor a pending future" in msg
        assert "benchmark function" not in msg

    def test_an_explicit_error_is_kept_verbatim(self) -> None:
        """How the serial site names the cause it alone can see."""
        error = WorkerReturnedNothingError("the worker returned None, and I saw it")
        job_future = JobFuture(job=_job(), error=error)
        assert job_future.state == Broken(error)
        with pytest.raises(WorkerReturnedNothingError) as exc_info:
            job_future.result()
        assert exc_info.value is error

    def test_a_future_resolving_to_none_raises_too(self) -> None:
        """The pooled path: same error, same message, same job id."""
        future: Future = Future()
        future.set_result(None)
        with pytest.raises(WorkerReturnedNothingError, match="job-42"):
            JobFuture(job=_job("job-42"), future=future).result()

    def test_a_broken_serial_result_is_never_cached(self) -> None:
        """Pre-P5 semantics preserved: `cache.set` only for a non-None result."""
        cache = _RecordingCache()
        with pytest.raises(WorkerReturnedNothingError):
            JobFuture(job=_job(), cache=cache).result()
        assert cache.sets == []

    def test_a_future_resolving_to_none_is_never_cached(self) -> None:
        cache = _RecordingCache()
        future: Future = Future()
        future.set_result(None)
        with pytest.raises(WorkerReturnedNothingError):
            JobFuture(job=_job(), future=future, cache=cache).result()
        assert cache.sets == []

    def test_an_empty_dict_is_a_valid_result(self) -> None:
        """A worker with no result vars returns ``{}`` -- falsy but not missing."""
        assert JobFuture(job=_job(), res={}).state == Ready({})

    def test_a_worker_raised_contract_error_is_not_the_harness_diagnosis(self) -> None:
        """The distinction store_results' handler ordering depends on.

        A ``WorkerContractError`` from the worker propagates out of ``result()``
        untouched; only ``WorkerReturnedNothingError`` is the harness's own verdict,
        and only that one is exempt from ``catch=``.
        """
        future: Future = Future()
        future.set_exception(WorkerContractError("raised by the worker"))
        with pytest.raises(WorkerContractError, match="raised by the worker") as exc_info:
            JobFuture(job=_job(), future=future).result()
        assert not isinstance(exc_info.value, WorkerReturnedNothingError)


class TestJobFunctionCacheJobIds:
    """``call_count`` was initialised to 0 and incremented nowhere, so every
    ``JobFunctionCache.call()`` produced the same job id -- and job ids are what
    every log line and contract-violation message identifies a sample by."""

    def test_each_call_gets_a_distinct_job_id(self) -> None:
        seen = []
        cache = JobFunctionCache(lambda **kw: dict(kw), cache_name="test_job_ids")
        try:
            cache.clear_cache()
            for i in range(3):
                seen.append(cache.call(var1=i).job.job_id)
        finally:
            cache.close()
        assert len(set(seen)) == 3, seen
        assert all(isinstance(job_id, str) for job_id in seen)


class TestClearTagWithoutACache:
    """``clear_tag`` on a cache-less FutureCache used to be an AttributeError.

    Not crashing is right -- but it must not be *silent* either: the public route
    (``Bench.clear_tag_from_sample_cache``) is reachable from user code, where
    "nothing happened" must not read as "the tag was cleared".
    """

    def test_it_does_not_raise(self) -> None:
        cache = FutureCache(cache_samples=False)
        try:
            cache.clear_tag("some_tag")  # used to be AttributeError on None
        finally:
            cache.close()

    def test_it_warns_that_there_was_nothing_to_clear(self, caplog) -> None:
        cache = FutureCache(cache_samples=False)
        try:
            with caplog.at_level(logging.WARNING, logger="bencher.job"):
                cache.clear_tag("some_tag")
        finally:
            cache.close()
        assert "some_tag" in caplog.text
        assert "does not exist" in caplog.text


if __name__ == "__main__":
    TestJob().test_bench_runner_parallel(True).report.show()
