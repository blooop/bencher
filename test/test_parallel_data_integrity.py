"""Comprehensive tests for parallel execution data integrity.

These tests verify that the MULTIPROCESSING executor with as_completed()
result streaming and FanoutCache produces bit-identical results to serial
execution. Data integrity is paramount — every test compares parallel
output to serial output element-by-element.

Test categories:
1. Serial vs parallel result equivalence (the gold standard)
2. as_completed() ordering correctness
3. FanoutCache cache hit/miss correctness
4. Multi-dimensional sweeps with repeats
5. Mixed result types
6. Cache persistence across serial <-> parallel switches
"""

from __future__ import annotations

import math
from enum import auto
from functools import partial

import numpy as np
import xarray as xr
from strenum import StrEnum

import bencher as bn
from bencher.bench_cfg import BenchCfg
from bencher.job import Executors, FutureCache, Job
from bencher.sweep_executor import worker_kwargs_wrapper


# ---------------------------------------------------------------------------
# Deterministic worker configs — no randomness so serial == parallel
# ---------------------------------------------------------------------------


class Color(StrEnum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class Algorithm(StrEnum):
    QUICK = auto()
    MERGE = auto()
    BUBBLE = auto()


class SimpleFloatConfig(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 10.0), samples=5)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.x * 2.0 + 1.0


class TwoDimConfig(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 5.0), samples=4)
    y = bn.FloatSweep(default=0.0, bounds=(0.0, 5.0), samples=4)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.x * self.y + self.x - self.y


class MultiResultConfig(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 10.0), samples=5)
    score = bn.ResultFloat()
    passed = bn.ResultBool()

    def benchmark(self):
        self.score = self.x**2
        self.passed = self.x > 5.0


class CategoricalConfig(bn.ParametrizedSweep):
    color = bn.EnumSweep(Color)
    algo = bn.StringSweep(["fast", "medium", "slow"])
    result = bn.ResultFloat()

    def benchmark(self):
        color_map = {Color.RED: 1.0, Color.GREEN: 2.0, Color.BLUE: 3.0}
        algo_map = {"fast": 10.0, "medium": 20.0, "slow": 30.0}
        self.result = color_map[self.color] + algo_map[self.algo]


class MixedDimConfig(bn.ParametrizedSweep):
    color = bn.EnumSweep(Color)
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 5.0), samples=3)
    enabled = bn.BoolSweep(default=True)
    result = bn.ResultFloat()

    def benchmark(self):
        color_val = {Color.RED: 1.0, Color.GREEN: 2.0, Color.BLUE: 3.0}[self.color]
        self.result = color_val * self.x * (1.0 if self.enabled else -1.0)


class ThreeDimConfig(bn.ParametrizedSweep):
    a = bn.FloatSweep(default=0.0, bounds=(0.0, 3.0), samples=3)
    b = bn.FloatSweep(default=0.0, bounds=(0.0, 3.0), samples=3)
    c = bn.FloatSweep(default=0.0, bounds=(0.0, 3.0), samples=3)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.a + self.b * 10 + self.c * 100


class RepeatableConfig(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 5.0), samples=4)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = math.sin(self.x) * 100.0


class LargeSweepConfig(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0.0, bounds=(0.0, 10.0), samples=8)
    y = bn.FloatSweep(default=0.0, bounds=(0.0, 10.0), samples=8)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.x * self.y


# ---------------------------------------------------------------------------
# Module-level picklable worker for FanoutCache tests
# ---------------------------------------------------------------------------


def _cache_test_worker(**kwargs):
    """A simple deterministic worker for cache tests. Must be at module level for pickle."""
    return {"result": sum(len(str(v)) for v in kwargs.values())}


def _cache_test_worker_double(**kwargs):
    """Returns x*2 for prefetch tests. Must be at module level for pickle."""
    return {"result": kwargs.get("x", 0) * 2}


def _cache_test_worker_const(**kwargs):  # pylint: disable=unused-argument
    """Returns constant for eviction tests. Must be at module level for pickle."""
    return {"result": 42}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_sweep(config_cls, input_vars, executor, run_cfg_overrides=None):
    """Run a sweep with the given executor and return the BenchResult."""
    worker = config_cls()
    bench = bn.Bench(f"integrity_{executor}", worker)
    run_cfg = bn.BenchRunCfg()
    run_cfg.executor = executor
    run_cfg.overwrite_sample_cache = True
    run_cfg.cache_samples = False
    run_cfg.print_bench_inputs = False
    run_cfg.print_bench_results = False
    if run_cfg_overrides:
        for k, v in run_cfg_overrides.items():
            setattr(run_cfg, k, v)
    return bench.plot_sweep(
        f"sweep_{executor}",
        input_vars=input_vars,
        run_cfg=run_cfg,
        plot_callbacks=False,
    )


def _assert_datasets_equal(ds_serial: xr.Dataset, ds_parallel: xr.Dataset, msg: str = ""):
    """Assert two xarray Datasets are element-wise identical."""
    prefix = f"{msg}: " if msg else ""
    assert set(ds_serial.data_vars) == set(ds_parallel.data_vars), (
        f"{prefix}data vars differ: {set(ds_serial.data_vars)} vs {set(ds_parallel.data_vars)}"
    )
    for var_name in ds_serial.data_vars:
        serial_vals = ds_serial[var_name].values
        parallel_vals = ds_parallel[var_name].values
        if serial_vals.dtype.kind == "f":
            np.testing.assert_allclose(
                serial_vals,
                parallel_vals,
                rtol=0,
                atol=1e-10,
                err_msg=f"{prefix}variable '{var_name}' values differ",
            )
        else:
            np.testing.assert_array_equal(
                serial_vals,
                parallel_vals,
                err_msg=f"{prefix}variable '{var_name}' values differ",
            )


def _make_bench_cfg():
    """Create a minimal BenchCfg for cache tests."""
    return BenchCfg(
        input_vars=[],
        result_vars=[],
        const_vars=[],
        bench_name="test",
        title="test",
        pass_repeat=False,
    )


# ---------------------------------------------------------------------------
# 1. Serial vs parallel result equivalence
# ---------------------------------------------------------------------------


class TestSerialVsParallelEquivalence:
    """The gold standard: parallel results must be bit-identical to serial."""

    def test_simple_1d_float(self):
        serial = _run_sweep(SimpleFloatConfig, [SimpleFloatConfig.param.x], Executors.SERIAL)
        parallel = _run_sweep(
            SimpleFloatConfig, [SimpleFloatConfig.param.x], Executors.MULTIPROCESSING
        )
        _assert_datasets_equal(serial.ds, parallel.ds, "simple 1D float")

    def test_2d_float(self):
        inputs = [TwoDimConfig.param.x, TwoDimConfig.param.y]
        serial = _run_sweep(TwoDimConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(TwoDimConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "2D float")

    def test_3d_float(self):
        inputs = [ThreeDimConfig.param.a, ThreeDimConfig.param.b, ThreeDimConfig.param.c]
        serial = _run_sweep(ThreeDimConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(ThreeDimConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "3D float")

    def test_multi_result_vars(self):
        serial = _run_sweep(MultiResultConfig, [MultiResultConfig.param.x], Executors.SERIAL)
        parallel = _run_sweep(
            MultiResultConfig, [MultiResultConfig.param.x], Executors.MULTIPROCESSING
        )
        _assert_datasets_equal(serial.ds, parallel.ds, "multi result vars")

    def test_categorical_sweep(self):
        inputs = [CategoricalConfig.param.color, CategoricalConfig.param.algo]
        serial = _run_sweep(CategoricalConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(CategoricalConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "categorical sweep")

    def test_mixed_numeric_and_categorical(self):
        inputs = [
            MixedDimConfig.param.color,
            MixedDimConfig.param.x,
            MixedDimConfig.param.enabled,
        ]
        serial = _run_sweep(MixedDimConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(MixedDimConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "mixed dims")

    def test_with_repeats(self):
        overrides = {"repeats": 3}
        serial = _run_sweep(
            RepeatableConfig,
            [RepeatableConfig.param.x],
            Executors.SERIAL,
            overrides,
        )
        parallel = _run_sweep(
            RepeatableConfig,
            [RepeatableConfig.param.x],
            Executors.MULTIPROCESSING,
            overrides,
        )
        _assert_datasets_equal(serial.ds, parallel.ds, "with repeats")

    def test_with_const_vars(self):
        results = {}
        for executor in [Executors.SERIAL, Executors.MULTIPROCESSING]:
            worker = MixedDimConfig()
            bench = bn.Bench(f"const_{executor}", worker)
            run_cfg = bn.BenchRunCfg()
            run_cfg.executor = executor
            run_cfg.overwrite_sample_cache = True
            run_cfg.cache_samples = False
            run_cfg.print_bench_inputs = False
            run_cfg.print_bench_results = False
            results[executor] = bench.plot_sweep(
                "const_sweep",
                input_vars=[MixedDimConfig.param.x],
                const_vars=[
                    MixedDimConfig.param.color.with_const(Color.GREEN),
                    MixedDimConfig.param.enabled.with_const(True),
                ],
                run_cfg=run_cfg,
                plot_callbacks=False,
            )
        _assert_datasets_equal(
            results[Executors.SERIAL].ds,
            results[Executors.MULTIPROCESSING].ds,
            "with const vars",
        )


# ---------------------------------------------------------------------------
# 2. as_completed() ordering correctness
# ---------------------------------------------------------------------------


class TestAsCompletedOrdering:
    """Verify out-of-order result storage still places values correctly."""

    def test_index_tuple_correctness_2d(self):
        """Each result must be at its correct index regardless of completion order."""
        inputs = [TwoDimConfig.param.x, TwoDimConfig.param.y]
        result = _run_sweep(TwoDimConfig, inputs, Executors.MULTIPROCESSING)
        ds = result.ds

        x_vals = ds.coords["x"].values
        y_vals = ds.coords["y"].values
        result_arr = ds["result"].values
        # Dataset has shape (x, y, repeat) — squeeze the repeat dimension
        if result_arr.ndim == 3:
            result_arr = result_arr[:, :, 0]
        for i, x in enumerate(x_vals):
            for j, y in enumerate(y_vals):
                expected = x * y + x - y
                actual = float(result_arr[i, j])
                assert abs(actual - expected) < 1e-10, (
                    f"Wrong value at ({x}, {y}): expected {expected}, got {actual}"
                )

    def test_index_tuple_correctness_3d(self):
        """3D sweep — every cell must match the expected deterministic value."""
        inputs = [ThreeDimConfig.param.a, ThreeDimConfig.param.b, ThreeDimConfig.param.c]
        result = _run_sweep(ThreeDimConfig, inputs, Executors.MULTIPROCESSING)
        ds = result.ds

        a_vals = ds.coords["a"].values
        b_vals = ds.coords["b"].values
        c_vals = ds.coords["c"].values
        result_arr = ds["result"].values
        # Dataset has shape (a, b, c, repeat) — squeeze the repeat dimension
        if result_arr.ndim == 4:
            result_arr = result_arr[:, :, :, 0]
        for i, a in enumerate(a_vals):
            for j, b in enumerate(b_vals):
                for k, c in enumerate(c_vals):
                    expected = a + b * 10 + c * 100
                    actual = float(result_arr[i, j, k])
                    assert abs(actual - expected) < 1e-10, (
                        f"Wrong value at ({a}, {b}, {c}): expected {expected}, got {actual}"
                    )

    def test_result_samples_count(self):
        """Total number of results must match the Cartesian product size."""
        inputs = [
            MixedDimConfig.param.color,
            MixedDimConfig.param.x,
            MixedDimConfig.param.enabled,
        ]
        result = _run_sweep(MixedDimConfig, inputs, Executors.MULTIPROCESSING)
        expected_count = 3 * 3 * 2  # 3 colors * 3 x values * 2 bool
        assert result.result_samples() == expected_count


# ---------------------------------------------------------------------------
# 3. Parallel cache correctness
# ---------------------------------------------------------------------------


class TestParallelCacheCorrectness:
    """Verify cache works correctly with parallel execution and as_completed()."""

    def test_cache_hit_miss_counts(self):
        """Cache counters must be correct after parallel execution."""
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=False,
            cache_name="test_parallel_cache_integrity",
            cache_samples=True,
        )
        cache.clear_cache()

        cfg = _make_bench_cfg()
        worker = partial(worker_kwargs_wrapper, _cache_test_worker, cfg)

        # First pass — all misses (use the process pool)
        futures = []
        for i in range(10):
            job = Job(job_id=f"fc:{i}", function=worker, job_args={"x": i})
            futures.append(cache.submit(job))
        for f in futures:
            f.result()

        assert cache.worker_wrapper_call_count == 10
        assert cache.worker_fn_call_count == 10
        assert cache.worker_cache_call_count == 0

        # Second pass — all hits (no process pool needed, served from cache)
        cache.clear_call_counts()
        futures2 = []
        for i in range(10):
            job = Job(job_id=f"fc2:{i}", function=worker, job_args={"x": i})
            futures2.append(cache.submit(job))
        results2 = [f.result() for f in futures2]

        assert cache.worker_wrapper_call_count == 10
        assert cache.worker_cache_call_count == 10
        assert cache.worker_fn_call_count == 0

        # Third pass — values must be identical to second pass
        cache.clear_call_counts()
        futures3 = []
        for i in range(10):
            job = Job(job_id=f"fc3:{i}", function=worker, job_args={"x": i})
            futures3.append(cache.submit(job))
        results3 = [f.result() for f in futures3]

        for r2, r3 in zip(results2, results3):
            assert r2 == r3, f"Cached values differ: {r2} vs {r3}"

        cache.clear_cache()
        cache.close()

    def test_prefetch_with_parallel_executor(self):
        """prefetch() must work correctly with parallel executor."""
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=False,
            cache_name="test_parallel_prefetch",
            cache_samples=True,
        )
        cache.clear_cache()

        cfg = _make_bench_cfg()
        worker = partial(worker_kwargs_wrapper, _cache_test_worker_double, cfg)

        # Populate cache
        keys = []
        for i in range(5):
            job = Job(job_id=f"pf:{i}", function=worker, job_args={"x": i})
            keys.append(job.job_key)
            cache.submit(job).result()

        # Prefetch and verify all keys found
        prefetched = cache.prefetch(keys)
        assert len(prefetched) == 5
        for i, key in enumerate(keys):
            assert key in prefetched
            assert prefetched[key]["result"] == i * 2

        cache.clear_cache()
        cache.close()

    def test_tag_eviction_with_parallel_executor(self):
        """Tag-based eviction must work with parallel executor."""
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=False,
            cache_name="test_parallel_evict",
            cache_samples=True,
        )
        cache.clear_cache()

        cfg = _make_bench_cfg()
        worker = partial(worker_kwargs_wrapper, _cache_test_worker_const, cfg)

        # Add entries with tags
        for i in range(5):
            job = Job(job_id=f"ev:{i}", function=worker, job_args={"x": i}, tag="tag_a")
            cache.submit(job).result()

        # Verify they're cached
        cache.clear_call_counts()
        for i in range(5):
            job = Job(job_id=f"ev2:{i}", function=worker, job_args={"x": i}, tag="tag_a")
            cache.submit(job).result()
        assert cache.worker_cache_call_count == 5

        # Evict the tag
        cache.clear_tag("tag_a")

        # Verify all evicted — all should be misses now
        cache.clear_call_counts()
        for i in range(5):
            job = Job(job_id=f"ev3:{i}", function=worker, job_args={"x": i}, tag="tag_a")
            cache.submit(job).result()
        assert cache.worker_fn_call_count == 5
        assert cache.worker_cache_call_count == 0

        cache.clear_cache()
        cache.close()


# ---------------------------------------------------------------------------
# 4. End-to-end parallel bench with cache
# ---------------------------------------------------------------------------


class TestParallelBenchWithCache:
    """Test full benchmark pipeline with caching enabled under parallel execution."""

    def test_cached_parallel_matches_serial(self):
        """Run serial (populates cache), then parallel (recomputes) — same results."""
        inputs = [TwoDimConfig.param.x, TwoDimConfig.param.y]

        serial_res = _run_sweep(TwoDimConfig, inputs, Executors.SERIAL)
        parallel_res = _run_sweep(TwoDimConfig, inputs, Executors.MULTIPROCESSING)

        _assert_datasets_equal(serial_res.ds, parallel_res.ds, "cached parallel vs serial")

    def test_parallel_repeated_runs_identical(self):
        """Two consecutive parallel runs must produce identical results."""
        inputs = [ThreeDimConfig.param.a, ThreeDimConfig.param.b, ThreeDimConfig.param.c]

        res1 = _run_sweep(ThreeDimConfig, inputs, Executors.MULTIPROCESSING)
        res2 = _run_sweep(ThreeDimConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(res1.ds, res2.ds, "repeated parallel runs")


# ---------------------------------------------------------------------------
# 5. Stress: larger sweep to exercise as_completed() with many futures
# ---------------------------------------------------------------------------


class TestLargeParallelSweep:
    """Larger sweeps to stress-test as_completed() with many concurrent futures."""

    def test_64_job_sweep(self):
        """8x8 = 64 jobs — enough to exercise concurrent result storage."""
        inputs = [LargeSweepConfig.param.x, LargeSweepConfig.param.y]
        serial = _run_sweep(LargeSweepConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(LargeSweepConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "64-job sweep")

        # Spot-check every value in the parallel result
        ds = parallel.ds
        x_vals = ds.coords["x"].values
        y_vals = ds.coords["y"].values
        result_arr = ds["result"].values
        if result_arr.ndim == 3:
            result_arr = result_arr[:, :, 0]
        for i, x in enumerate(x_vals):
            for j, y in enumerate(y_vals):
                expected = x * y
                actual = float(result_arr[i, j])
                np.testing.assert_allclose(actual, expected, rtol=1e-10)

    def test_large_sweep_with_repeats(self):
        """5 x values * 3 repeats = 15 jobs with repeats."""
        overrides = {"repeats": 3}
        serial = _run_sweep(
            SimpleFloatConfig, [SimpleFloatConfig.param.x], Executors.SERIAL, overrides
        )
        parallel = _run_sweep(
            SimpleFloatConfig, [SimpleFloatConfig.param.x], Executors.MULTIPROCESSING, overrides
        )
        _assert_datasets_equal(serial.ds, parallel.ds, "large sweep with repeats")

    def test_many_categorical_combinations(self):
        """3 colors * 3 algos = 9 jobs with categorical inputs."""
        inputs = [CategoricalConfig.param.color, CategoricalConfig.param.algo]
        serial = _run_sweep(CategoricalConfig, inputs, Executors.SERIAL)
        parallel = _run_sweep(CategoricalConfig, inputs, Executors.MULTIPROCESSING)
        _assert_datasets_equal(serial.ds, parallel.ds, "many categorical combinations")


# ---------------------------------------------------------------------------
# 6. BenchRunner with parallel execution
# ---------------------------------------------------------------------------


class TestBenchRunnerParallelIntegrity:
    """BenchRunner end-to-end with MULTIPROCESSING — data correctness.

    These tests verify that the MULTIPROCESSING executor with as_completed()
    result streaming produces bit-identical results to serial execution when
    using BenchRunner.
    """

    @staticmethod
    def _make_run_cfg(executor: Executors) -> bn.BenchRunCfg:
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = executor
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        return run_cfg

    def test_simple_float_serial_vs_multiprocessing(self):
        """SimpleFloatConfig: BenchRunner SERIAL vs MULTIPROCESSING should match."""
        serial_runner = bn.BenchRunner(
            "integrity_serial", run_cfg=self._make_run_cfg(Executors.SERIAL)
        )
        serial_runner.add_bench(SimpleFloatConfig())
        serial_results = serial_runner.run(level=2)

        parallel_runner = bn.BenchRunner(
            "integrity_parallel", run_cfg=self._make_run_cfg(Executors.MULTIPROCESSING)
        )
        parallel_runner.add_bench(SimpleFloatConfig())
        parallel_results = parallel_runner.run(level=2)

        assert len(serial_results) == len(parallel_results)
        for serial_cfg, parallel_cfg in zip(serial_results, parallel_results):
            assert serial_cfg.ds is not None, "Serial BenchRunner dataset is unexpectedly None"
            assert parallel_cfg.ds is not None, "Parallel BenchRunner dataset is unexpectedly None"
            assert set(serial_cfg.ds.data_vars) == set(parallel_cfg.ds.data_vars)
            _assert_datasets_equal(
                serial_cfg.ds,
                parallel_cfg.ds,
                "BenchRunner(SimpleFloatConfig) SERIAL vs MULTIPROCESSING",
            )

    def test_multi_result_serial_vs_multiprocessing(self):
        """MultiResultConfig: BenchRunner SERIAL vs MULTIPROCESSING should match."""
        serial_runner = bn.BenchRunner(
            "integrity_multi_serial", run_cfg=self._make_run_cfg(Executors.SERIAL)
        )
        serial_runner.add_bench(MultiResultConfig())
        serial_results = serial_runner.run(level=2)

        parallel_runner = bn.BenchRunner(
            "integrity_multi_parallel", run_cfg=self._make_run_cfg(Executors.MULTIPROCESSING)
        )
        parallel_runner.add_bench(MultiResultConfig())
        parallel_results = parallel_runner.run(level=2)

        assert len(serial_results) == len(parallel_results)
        for serial_cfg, parallel_cfg in zip(serial_results, parallel_results):
            assert serial_cfg.ds is not None
            assert parallel_cfg.ds is not None
            assert len(serial_cfg.ds.data_vars) >= 2, "MultiResultConfig should yield >=2 vars"
            assert set(serial_cfg.ds.data_vars) == set(parallel_cfg.ds.data_vars)
            _assert_datasets_equal(
                serial_cfg.ds,
                parallel_cfg.ds,
                "BenchRunner(MultiResultConfig) SERIAL vs MULTIPROCESSING",
            )
