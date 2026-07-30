"""Plan 21 — one failing sample must not discard a whole sweep.

``Bench.optimize(catch=...)`` has had this knob since #962; the sweep path, which
is the common one, had no equivalent spelling, so the same benchmark was
fault-tolerant when driven by Optuna and all-or-nothing when swept.

The default must stay fail-fast, and tolerance without accounting would be worse
than fail-fast: a run in which every sample failed would otherwise produce an
all-sentinel dataset, a valid-looking report and a successful exit. ``catch`` and
``fail_on_sample_error`` are tested here as the pair they are.
"""

from __future__ import annotations

import pickle
import unittest
from typing import ClassVar

import numpy as np

import bencher as bn
from bencher.bencher import _enforce_sample_error_policy
from bencher.job import Executors


class Flaky(bn.ParametrizedSweep):
    """Raises for the input values named in ``fail_at``."""

    x = bn.IntSweep(default=0, bounds=(0, 3), samples=4)
    y = bn.ResultFloat()

    fail_at: tuple = ()
    exc_type: type[Exception] = RuntimeError

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        if self.x in type(self).fail_at:
            raise type(self).exc_type(f"x={self.x} is cursed")
        self.y = float(self.x) * 2.0
        return super().__call__(**kwargs)


class Counting(bn.ParametrizedSweep):
    """Records every call, so a re-execution after a caught failure is countable.

    Module level on purpose: the sample cache pickles the worker, and a locally
    defined class cannot be pickled.
    """

    x = bn.IntSweep(default=0, bounds=(0, 1), samples=2)
    y = bn.ResultFloat()

    # Shared across instances on purpose: the worker is re-created per sample, so
    # a per-instance counter could not observe how many times it ran.
    calls: ClassVar[list] = []

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        type(self).calls.append(self.x)
        if self.x == 1:
            raise RuntimeError("boom")
        self.y = 1.0
        return super().__call__(**kwargs)


def _run(fail_at=(), exc_type=RuntimeError, *, executor=Executors.SERIAL, **run_kwargs):
    Flaky.fail_at = tuple(fail_at)
    Flaky.exc_type = exc_type
    cfg = bn.BenchRunCfg(executor=executor, **run_kwargs)
    cfg.auto_plot = False
    cfg.cache_results = False
    cfg.cache_samples = False
    bench = Flaky().to_bench(cfg)
    try:
        return bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
    finally:
        Flaky.fail_at = ()
        bench.close()


class TestDefaultIsFailFast(unittest.TestCase):
    """P1, pinned as a regression test: the default behaviour is unchanged."""

    def test_an_uncaught_exception_propagates_out_of_the_sweep(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            _run(fail_at=(2,))
        self.assertIn("cursed", str(ctx.exception))

    def test_a_clean_sweep_records_no_failures(self) -> None:
        res = _run()
        self.assertEqual(res.n_failed, 0)
        self.assertEqual(res.failed_samples, [])
        self.assertEqual(res.failed_fraction, 0.0)

    def test_catch_defaults_to_empty(self) -> None:
        self.assertEqual(bn.BenchRunCfg().catch, ())
        self.assertIs(bn.BenchRunCfg().fail_on_sample_error, False)


class TestCatch(unittest.TestCase):
    """D1/D2 — the sweep completes, the failed coordinate carries the sentinel."""

    def test_one_failure_out_of_four_does_not_lose_the_others(self) -> None:
        res = _run(fail_at=(2,), catch=(RuntimeError,))
        self.assertEqual(res.n_failed, 1)
        values = res.ds["y"].values.reshape(-1)
        self.assertEqual(len(values), 4, "the dataset shape must be unchanged")
        self.assertTrue(np.isnan(values[2]), "the failed coordinate must hold the fill")
        for i in (0, 1, 3):
            self.assertEqual(values[i], i * 2.0, f"successful sample {i} was lost")

    def test_the_failure_records_the_inputs_and_the_exception(self) -> None:
        res = _run(fail_at=(2,), catch=(RuntimeError,))
        (failure,) = res.failed_samples
        self.assertEqual(failure.inputs.get("x"), 2)
        self.assertIn("cursed", failure.exception)
        self.assertIn("RuntimeError", failure.exception)
        self.assertIn("Traceback", failure.traceback)
        self.assertTrue(failure.job_id)

    def test_an_unlisted_exception_type_still_aborts(self) -> None:
        with self.assertRaises(ValueError):
            _run(fail_at=(1,), exc_type=ValueError, catch=(RuntimeError,))

    def test_a_parent_class_in_catch_covers_a_subclass(self) -> None:
        res = _run(fail_at=(1,), exc_type=ValueError, catch=(Exception,))
        self.assertEqual(res.n_failed, 1)

    def test_every_sample_failing_still_completes(self) -> None:
        """Documented, and exactly why fail_on_sample_error exists."""
        res = _run(fail_at=(0, 1, 2, 3), catch=(RuntimeError,))
        self.assertEqual(res.n_failed, 4)
        self.assertTrue(np.all(np.isnan(res.ds["y"].values)))
        self.assertEqual(res.failed_fraction, 1.0)

    def test_a_warning_is_logged_naming_the_inputs(self) -> None:
        import logging

        with self.assertLogs("bencher.result_collector", level=logging.WARNING) as logs:
            _run(fail_at=(2,), catch=(RuntimeError,))
        self.assertTrue(any("x=2" in line for line in logs.output), logs.output)

    def test_plot_sweep_catch_argument_reaches_the_run_cfg(self) -> None:
        Flaky.fail_at = (2,)
        cfg = bn.BenchRunCfg()
        cfg.auto_plot = False
        cfg.cache_results = False
        cfg.cache_samples = False
        bench = Flaky().to_bench(cfg)
        try:
            res = bench.plot_sweep(
                input_vars=["x"],
                result_vars=["y"],
                catch=(RuntimeError,),
                plot_callbacks=False,
            )
        finally:
            Flaky.fail_at = ()
            bench.close()
        self.assertEqual(res.n_failed, 1)


class TestBothExecutorPaths(unittest.TestCase):
    """The two paths raise in *different places*, so both need their own catch.

    The serial executor runs the worker inside ``FutureCache.submit``, so a raising
    sample never reaches ``store_results`` at all -- catching only at
    ``JobFuture.result()`` would leave the default executor fail-fast while a pool
    run tolerated failures. The serial site is exercised by every other test in
    this file (``Executors.SERIAL`` is the default); this drives the pool site
    directly with a future that holds an exception, which is deterministic and does
    not need a subprocess.
    """

    def _pool_store(self, catch):
        from concurrent.futures import Future

        from bencher.job import Job, JobFuture
        from bencher.result_collector import ResultCollector

        res = _run(catch=catch)  # a clean run to build a real dataset + cfg
        collector = ResultCollector()
        future = Future()
        future.set_exception(RuntimeError("pool boom"))
        job = Job(job_id="pool-job", function=lambda **_: None, job_args={"x": 1})
        job_future = JobFuture(job=job, future=future)

        class Worker:
            function_input: ClassVar[dict] = {"x": 1}
            index_tuple = (0, 0)

        cfg = bn.BenchRunCfg(catch=catch)
        collector.store_results(job_future, res, Worker(), cfg, None)
        return res

    def test_the_pool_path_tolerates_a_failure(self) -> None:
        res = self._pool_store((RuntimeError,))
        self.assertEqual(res.n_failed, 1)
        (failure,) = res.failed_samples
        self.assertIn("pool boom", failure.exception)
        self.assertEqual(failure.inputs, {"x": 1})

    def test_the_pool_path_still_aborts_without_catch(self) -> None:
        with self.assertRaises(RuntimeError):
            self._pool_store(())

    def test_the_pool_path_still_aborts_for_an_unlisted_type(self) -> None:
        with self.assertRaises(RuntimeError):
            self._pool_store((ValueError,))


class TestNoCacheOnFailure(unittest.TestCase):
    """D4, the highest-severity risk: a cached failure would be durable and silent."""

    def test_a_caught_sample_is_not_written_to_the_sample_cache(self) -> None:
        """A second run with the same key must re-execute it.

        A cached failure would be durable and silent -- the highest-severity risk in
        the whole feature, since it turns one transient flake into a permanently
        broken coordinate for every later run.
        """
        Counting.calls = []
        cfg = bn.BenchRunCfg(catch=(RuntimeError,), cache_samples=True)
        cfg.auto_plot = False
        cfg.cache_results = False
        bench = Counting().to_bench(cfg)
        try:
            bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
            first = list(Counting.calls)
            bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
        finally:
            bench.close()
        second = Counting.calls[len(first) :]
        self.assertIn(1, second, "the failed sample was cached and never retried")
        self.assertNotIn(0, second, "the successful sample should have come from cache")


class TestFailOnSampleError(unittest.TestCase):
    """D3 — the accounting that makes catch= safe to use unattended."""

    def test_true_raises_when_any_sample_failed(self) -> None:
        with self.assertRaises(bn.SampleErrorPolicyError) as ctx:
            _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=True)
        self.assertIn("1 sample(s) failed", str(ctx.exception))

    def test_true_does_not_raise_for_a_clean_run(self) -> None:
        res = _run(catch=(RuntimeError,), fail_on_sample_error=True)
        self.assertEqual(res.n_failed, 0)

    def test_a_fraction_below_the_threshold_does_not_raise(self) -> None:
        res = _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=0.5)
        self.assertEqual(res.n_failed, 1)
        self.assertLess(res.failed_fraction, 0.5)

    def test_a_fraction_at_the_threshold_raises(self) -> None:
        with self.assertRaises(bn.SampleErrorPolicyError):
            _run(fail_at=(1, 2), catch=(RuntimeError,), fail_on_sample_error=0.5)

    def test_an_out_of_range_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=1.5)

    def test_an_out_of_range_threshold_is_rejected_even_when_nothing_failed(self) -> None:
        """A config error must not wait for a sample failure to become visible.

        Validating the threshold only on the failing path made a typo -- 50 for
        "50%", say -- inert on every clean run, then surfaced it as a ValueError
        at the one moment the caller was trying to read a sample failure.
        """
        for bad in (1.5, 50, -0.2):
            with self.subTest(threshold=bad), self.assertRaises(ValueError):
                _run(catch=(RuntimeError,), fail_on_sample_error=bad)

    def test_zero_and_false_leave_the_policy_off(self) -> None:
        """Falsy thresholds are 'off', not 'out of range' -- unchanged by validation."""
        for off in (False, 0, 0.0):
            with self.subTest(policy=off):
                res = _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=off)
                self.assertEqual(res.n_failed, 1)

    def test_the_result_is_still_registered_before_the_raise(self) -> None:
        """Losing the artifact would defeat the point of catching."""
        Flaky.fail_at = (2,)
        cfg = bn.BenchRunCfg(catch=(RuntimeError,), fail_on_sample_error=True)
        cfg.auto_plot = False
        cfg.cache_results = False
        cfg.cache_samples = False
        bench = Flaky().to_bench(cfg)
        try:
            with self.assertRaises(bn.SampleErrorPolicyError):
                bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
            self.assertEqual(len(bench.results), 1)
            res = bench.get_result()
            self.assertEqual(res.n_failed, 1)
            self.assertEqual(res.ds["y"].values.reshape(-1)[0], 0.0)
        finally:
            Flaky.fail_at = ()
            bench.close()


class TestResultsCachedBeforeThisFeatureExisted(unittest.TestCase):
    """The accounting must survive a result that predates it.

    ``BenchResult`` objects are pickled into the benchmark cache, and unpickling
    restores ``__dict__`` without calling ``__init__``. A result cached by an
    earlier bencher therefore has no ``failed_samples`` and no ``n_attempted``,
    and ``run_sweep`` enforces the policy on the cache-hit path too -- so reading
    those attributes directly turned "upgrade, set fail_on_sample_error, hit a
    warm cache" into an AttributeError on a run that had nothing wrong with it.
    """

    def _revived_old_result(self) -> bn.BenchResult:
        res = _run()
        del res.failed_samples
        del res.n_attempted
        return pickle.loads(pickle.dumps(res))

    def test_the_accounting_reads_as_a_clean_run(self) -> None:
        revived = self._revived_old_result()
        self.assertEqual(revived.n_failed, 0)
        self.assertEqual(revived.failed_fraction, 0.0)

    def test_the_policy_does_not_raise_on_such_a_result(self) -> None:
        revived = self._revived_old_result()
        for policy in (False, True, 0.5):
            with self.subTest(policy=policy):
                _enforce_sample_error_policy(revived, policy)


class TestIdentityIsUnaffected(unittest.TestCase):
    def test_catch_does_not_move_the_cache_key(self) -> None:
        """It is a run-time policy, not part of what identifies the measurement."""
        keys = []
        for catch in ((), (RuntimeError,)):
            cfg = bn.BenchRunCfg(catch=catch)
            cfg.auto_plot = False
            cfg.cache_results = False
            cfg.cache_samples = False
            bench = Flaky().to_bench(cfg)
            try:
                res = bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
                keys.append(res.bench_cfg.hash_persistent(True))
            finally:
                bench.close()
        self.assertEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
