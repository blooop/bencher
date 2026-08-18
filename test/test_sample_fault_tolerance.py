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
from bencher.regression import detect_percentage


class Flaky(bn.ParametrizedSweep):
    """Raises for the input values named in ``fail_at``."""

    x = bn.IntSweep(default=0, bounds=(0, 3), samples=4)
    y = bn.ResultFloat()

    fail_at: tuple = ()
    exc_type: type[Exception] = RuntimeError

    def benchmark(self) -> None:
        if self.x in type(self).fail_at:
            raise type(self).exc_type(f"x={self.x} is cursed")
        self.y = float(self.x) * 2.0


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

    def benchmark(self) -> None:
        type(self).calls.append(self.x)
        if self.x == 1:
            raise RuntimeError("boom")
        self.y = 1.0


def _run(fail_at=(), exc_type=RuntimeError, *, executor=Executors.SERIAL, **run_kwargs):
    Flaky.fail_at = tuple(fail_at)
    Flaky.exc_type = exc_type
    cfg = bn.BenchRunCfg(execution=bn.ExecutionCfg(executor=executor, **run_kwargs))
    cfg.visualization.auto_plot = False
    cfg.cache.results = False
    cfg.cache.samples = False
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
        self.assertEqual(bn.BenchRunCfg().execution.catch, ())
        self.assertIs(bn.BenchRunCfg().execution.fail_on_sample_error, False)


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

    def test_catch_has_one_home(self) -> None:
        """``catch`` is run configuration and lives on ``BenchRunCfg`` only.

        ``run_cfg`` already reaches ``plot_sweep`` as an object; a second kwarg
        spelling would give the knob two homes and a precedence rule between
        them (A5 R1).
        """
        import inspect

        self.assertNotIn("catch", inspect.signature(bn.Bench.plot_sweep).parameters)
        self.assertNotIn("fail_on_sample_error", inspect.signature(bn.Bench.plot_sweep).parameters)


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

        cfg = bn.BenchRunCfg(execution=bn.ExecutionCfg(catch=catch))
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
        # The first sweep must be a cold miss or nothing executes and the test
        # asserts nothing; the second must *not* clear, or it clears the cache it
        # is meant to be reading. A sample cache left warm by an earlier run of
        # this file made this pass or fail depending on run order.
        cfg = bn.BenchRunCfg(
            execution=bn.ExecutionCfg(catch=(RuntimeError,)),
            cache=bn.CacheCfg(samples=True, clear_samples=True),
        )
        cfg.visualization.auto_plot = False
        cfg.cache.results = False
        bench = Counting().to_bench(cfg)
        try:
            bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
            first = list(Counting.calls)
            self.assertEqual(sorted(first), [0, 1], "the first sweep was not a cold miss")
            bench.run_cfg.cache.clear_samples = False
            bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
        finally:
            bench.close()
        second = Counting.calls[len(first) :]
        self.assertIn(1, second, "the failed sample was cached and never retried")
        self.assertNotIn(0, second, "the successful sample should have come from cache")


class TestTheFractionIsOverExecutedSamples(unittest.TestCase):
    """A cache hit never reached the worker, so it cannot be a failed *attempt*.

    Counting it made one ``fail_on_sample_error`` threshold mean different things
    on a cold and a warm cache: the single failure in a 4-sample sweep whose other
    three came from cache is 100% of what ran, and ``0.5`` used to pass it.
    """

    def _sweep(self, bench):
        return bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)

    def _bench(self, **kwargs):
        Flaky.fail_at = (2,)
        # clear_sample_cache starts on so a cache left warm by an earlier test run
        # cannot make the *first* sweep a partial cache hit; it is turned off after
        # that first sweep, or the second one would clear the cache it is meant to
        # be reading.
        cfg = bn.BenchRunCfg(
            execution=bn.ExecutionCfg(catch=(RuntimeError,), **kwargs),
            cache=bn.CacheCfg(samples=True, clear_samples=True),
        )
        cfg.visualization.auto_plot = False
        cfg.cache.results = False
        return Flaky().to_bench(cfg)

    def _second_sweep_reads_the_cache(self, bench) -> None:
        bench.run_cfg.cache.clear_samples = False

    def test_a_warm_cache_does_not_dilute_the_fraction(self) -> None:
        bench = self._bench()
        try:
            cold = self._sweep(bench)
            self.assertEqual((cold.n_failed, cold.n_attempted), (1, 4))
            self.assertEqual(cold.failed_fraction, 0.25)
            # Second sweep: 3 of 4 come from cache, only the failing one runs.
            self._second_sweep_reads_the_cache(bench)
            warm = self._sweep(bench)
            self.assertEqual((warm.n_failed, warm.n_attempted), (1, 1))
            self.assertEqual(warm.failed_fraction, 1.0)
        finally:
            Flaky.fail_at = ()
            bench.close()

    def test_a_threshold_that_passed_cold_fails_once_only_flakes_run(self) -> None:
        """The behavioural consequence, which is the whole point of the fraction."""
        bench = self._bench(fail_on_sample_error=0.5)
        try:
            self._sweep(bench)  # 1 of 4 executed failed -> 25%, under the threshold
            self._second_sweep_reads_the_cache(bench)
            with self.assertRaises(bn.SampleErrorPolicyError) as ctx:
                self._sweep(bench)  # 1 of 1 executed failed -> 100%
            self.assertIn("100%", str(ctx.exception))
        finally:
            Flaky.fail_at = ()
            bench.close()


class TestTheCacheHitPathIsNotThisRunsErrors(unittest.TestCase):
    """The policy must not fail a run on failures a *different* run produced.

    On a benchmark-result cache hit ``calculate_benchmark_results`` never runs, so
    the unpickled result still carries the first run's ``failed_samples`` and
    ``n_attempted``. Enforcing there raised for a run whose worker executed zero
    jobs -- and since ``only_plot`` forces ``cache_results``, for a pure re-plot
    too. ``n_failed`` still reports the holes, which is a different question.
    """

    def _bench(self, **kwargs):
        clear_cache = kwargs.pop("clear_cache", False)
        cfg = bn.BenchRunCfg(
            execution=bn.ExecutionCfg(catch=(RuntimeError,), **kwargs),
            cache=bn.CacheCfg(results=True, clear=clear_cache),
        )
        cfg.visualization.auto_plot = False
        cfg.cache.samples = False
        return Flaky().to_bench(cfg)

    def test_a_pure_cache_hit_does_not_raise_on_the_previous_runs_failures(self) -> None:
        Flaky.fail_at = (2,)
        first = self._bench(clear_cache=True)
        try:
            res = first.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
            self.assertEqual(res.n_failed, 1)
        finally:
            first.close()

        Flaky.fail_at = ()  # nothing in this run *can* fail
        second = self._bench(fail_on_sample_error=True)
        try:
            revived = second.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
        finally:
            second.close()
        # The loaded artifact still reports its holes -- it really does have one.
        self.assertEqual(revived.n_failed, 1)

    def test_the_policy_still_fires_for_a_run_that_actually_sampled(self) -> None:
        """The guard is 'did this run sample', not 'is caching on'."""
        Flaky.fail_at = (2,)
        bench = self._bench(clear_cache=True, fail_on_sample_error=True)
        try:
            with self.assertRaises(bn.SampleErrorPolicyError):
                bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
        finally:
            Flaky.fail_at = ()
            bench.close()


class TestCatchIsValidatedEagerly(unittest.TestCase):
    """``catch`` gets the same treatment as ``fail_on_sample_error``.

    Left unvalidated, a bare class surfaced as ``TypeError: 'type' object is not
    iterable`` and a string as ``catching classes that do not inherit from
    BaseException`` -- both from inside the sampling loop, with nothing in the
    message naming ``catch``.
    """

    def test_a_bare_exception_class_is_accepted_and_wrapped(self) -> None:
        res = _run(fail_at=(2,), catch=RuntimeError)
        self.assertEqual(res.n_failed, 1)

    def test_a_non_exception_type_is_rejected(self) -> None:
        """TypeError, because that is what ``except`` itself raises for one."""
        for bad in (str, 42, "RuntimeError", (ValueError, "nope")):
            with self.subTest(catch=bad), self.assertRaises(TypeError) as ctx:
                _run(fail_at=(2,), catch=bad)
            self.assertIn("catch", str(ctx.exception))

    def test_nothing_is_sampled_before_the_knobs_are_validated(self) -> None:
        """A typo must cost milliseconds, not a whole sweep.

        Both knobs are checked at the top of ``plot_sweep``; the threshold used to
        be range-checked only when the run had already finished, so an expensive
        sweep ran to completion before reporting a config error.
        """
        for kwargs in ({"catch": "RuntimeError"}, {"fail_on_sample_error": 50}):
            with self.subTest(**kwargs):
                Counting.calls = []
                cfg = bn.BenchRunCfg(
                    cache=bn.CacheCfg(samples=False), execution=bn.ExecutionCfg(**kwargs)
                )
                cfg.visualization.auto_plot = False
                cfg.cache.results = False
                bench = Counting().to_bench(cfg)
                try:
                    with self.assertRaises((TypeError, ValueError)):
                        bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
                finally:
                    bench.close()
                self.assertEqual(Counting.calls, [], "the sweep ran before validating")


class TestRegressionBoundary(unittest.TestCase):
    """D5 — regression detection must read a filled failure as absent, not as data.

    A tolerated failure writes the same missing sentinel that history uses for "not
    recorded", so the regression path must not read it as a measurement. It must
    also not read it as an *improvement*: NaN comparisons are all False, so an
    all-failed metric silently reports "no regression" -- which is why
    ``fail_on_sample_error`` and not the regression gate is what catches P4.
    """

    def test_a_filled_failure_does_not_move_the_baseline(self) -> None:
        clean = np.array([10.0, 10.1, 9.9, 10.05])
        with_hole = np.array([10.0, 10.1, np.nan, 9.9, 10.05])
        curr = np.array([10.0])
        self.assertEqual(
            detect_percentage("latency", clean, curr).baseline_value,
            detect_percentage("latency", with_hole, curr).baseline_value,
        )

    def test_a_filled_failure_is_not_read_as_a_regression(self) -> None:
        hist = np.array([10.0, 10.1, 9.9, 10.05])
        # One repeat of the current sample was caught; the others are unchanged.
        result = detect_percentage("latency", hist, np.array([10.0, np.nan, 10.1]))
        self.assertFalse(result.regressed)
        self.assertAlmostEqual(result.current_value, 10.05)

    def test_a_metric_whose_every_sample_failed_reports_no_measurement(self) -> None:
        """Fails safe (no false regression) but silent -- documented, not fixed here."""
        hist = np.array([10.0, 10.1, 9.9, 10.05])
        result = detect_percentage("latency", hist, np.array([np.nan, np.nan]))
        self.assertFalse(result.regressed)
        self.assertTrue(np.isnan(result.current_value))


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

    def test_a_truthy_integer_is_rejected_rather_than_guessed_at(self) -> None:
        """``1`` could mean True or 100%; bool being a subclass of int hides the choice.

        Left alone, ``1`` is truthy, is not ``True``, and becomes the 1.0 threshold --
        "raise only if *every* sample failed", the near-opposite of the "raise if any
        failed" that someone writing 1 (or feeding it from YAML) almost certainly
        meant. Floats stay unambiguous, so 1.0 still means 100%.
        """
        with self.assertRaises(ValueError) as ctx:
            _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=1)
        self.assertIn("ambiguous", str(ctx.exception))

    def test_one_point_zero_is_still_a_hundred_percent(self) -> None:
        res = _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=1.0)
        self.assertEqual(res.n_failed, 1)  # 1 of 4: below 100%, so no raise
        with self.assertRaises(bn.SampleErrorPolicyError):  # all 4 fail: 100%
            _run(fail_at=(0, 1, 2, 3), catch=(RuntimeError,), fail_on_sample_error=1.0)

    def test_zero_and_false_leave_the_policy_off(self) -> None:
        """Falsy thresholds are 'off', not 'out of range' -- unchanged by validation."""
        for off in (False, 0, 0.0):
            with self.subTest(policy=off):
                res = _run(fail_at=(2,), catch=(RuntimeError,), fail_on_sample_error=off)
                self.assertEqual(res.n_failed, 1)

    def test_the_result_is_still_registered_before_the_raise(self) -> None:
        """Losing the artifact would defeat the point of catching."""
        Flaky.fail_at = (2,)
        cfg = bn.BenchRunCfg(
            execution=bn.ExecutionCfg(catch=(RuntimeError,), fail_on_sample_error=True)
        )
        cfg.visualization.auto_plot = False
        cfg.cache.results = False
        cfg.cache.samples = False
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
            cfg = bn.BenchRunCfg(execution=bn.ExecutionCfg(catch=catch))
            cfg.visualization.auto_plot = False
            cfg.cache.results = False
            cfg.cache.samples = False
            bench = Flaky().to_bench(cfg)
            try:
                res = bench.plot_sweep(input_vars=["x"], result_vars=["y"], plot_callbacks=False)
                keys.append(res.bench_cfg.hash_persistent(True))
            finally:
                bench.close()
        self.assertEqual(keys[0], keys[1])


if __name__ == "__main__":
    unittest.main()
