"""Tests for multiprocessing executor correctness.

These tests verify that the entire Job → ProcessPoolExecutor → run_job
serialization pipeline works correctly with every sweep type, every
mutation method, and realistic BenchCfg/worker_kwargs_wrapper payloads.

The PR #854 bug (ListProxy pickle failure) only surfaced under
multiprocessing because ProcessPoolExecutor pickles Job objects to send
them to child processes.  Serial execution never pickles, so this class
of bugs is invisible without explicit multiprocessing testing.
"""

from __future__ import annotations

import pickle
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from enum import auto
from functools import partial
from pathlib import Path

from strenum import StrEnum

import bencher as bn
from bencher.bench_cfg import BenchCfg
from bencher.job import Job, run_job, FutureCache, Executors
from bencher.sweep_executor import worker_kwargs_wrapper
from bencher.worker_job import WorkerJob

# ---------------------------------------------------------------------------
# Test fixtures: sweep types, enums, worker configs
# ---------------------------------------------------------------------------

YAML_DICT = Path(__file__).resolve().parent.parent / "bencher" / "example" / "yaml_sweep_dict.yaml"


class Color(StrEnum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class Algorithm(StrEnum):
    QUICK = auto()
    MERGE = auto()
    HEAP = auto()
    BUBBLE = auto()


class MultiTypeConfig(bn.ParametrizedSweep):
    """Config with every sweep type for integration tests."""

    color = bn.EnumSweep(Color)
    label = bn.StringSweep(["fast", "medium", "slow"])
    enabled = bn.BoolSweep(default=True)
    count = bn.IntSweep(default=5, bounds=(1, 10))
    ratio = bn.FloatSweep(default=0.5, bounds=(0.0, 1.0), samples=5)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.count * self.ratio


class StringOnlyConfig(bn.ParametrizedSweep):
    """Config with string sweep — the type most affected by PR #854."""

    algorithm = bn.StringSweep(["quick", "merge", "heap", "bubble"])
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = len(self.algorithm)


class EnumOnlyConfig(bn.ParametrizedSweep):
    """Config with enum sweep."""

    algo = bn.EnumSweep(Algorithm)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = len(self.algo)


class BoolOnlyConfig(bn.ParametrizedSweep):
    """Config with bool sweep."""

    flag = bn.BoolSweep(default=True)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = 1.0 if self.flag else 0.0


class MixedSelectorConfig(bn.ParametrizedSweep):
    """Config mixing multiple selector types with numeric types."""

    color = bn.EnumSweep(Color)
    label = bn.StringSweep(["x", "y", "z"])
    active = bn.BoolSweep()
    weight = bn.FloatSweep(default=1.0, bounds=(0.0, 10.0), samples=3)
    result = bn.ResultFloat()

    def benchmark(self):
        self.result = self.weight * (1.0 if self.active else -1.0)


# ---------------------------------------------------------------------------
# Module-level functions for multiprocessing (must be picklable)
# ---------------------------------------------------------------------------


def _simple_worker(**kwargs) -> dict:
    """A simple worker function that returns its inputs as results."""
    return {"result": sum(len(str(v)) for v in kwargs.values())}


def _run_job_in_subprocess(job_bytes: bytes) -> dict:
    """Unpickle a Job and run it inside a subprocess."""
    job = pickle.loads(job_bytes)  # noqa: S301
    return run_job(job)


# ---------------------------------------------------------------------------
# 1. Job pickle: partial(worker_kwargs_wrapper, worker, bench_cfg) + job_args
# ---------------------------------------------------------------------------


class TestJobPickle:
    """The Job object (function + job_args) must survive pickle round-trip.

    In multiprocessing, executor.submit(run_job, job) pickles both run_job
    and the Job.  The Job.function is a partial capturing worker_kwargs_wrapper,
    the actual worker, and the full BenchCfg.
    """

    def _make_bench_cfg(self, input_vars, result_vars=None, const_vars=None):
        return BenchCfg(
            input_vars=input_vars or [],
            result_vars=result_vars or [],
            const_vars=const_vars or [],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

    def _make_job(self, bench_cfg, job_args):
        worker = partial(worker_kwargs_wrapper, _simple_worker, bench_cfg)
        return Job(
            job_id="test:1",
            function=worker,
            job_args=job_args,
        )

    def test_job_with_string_values(self):
        sw = bn.StringSweep(["a", "b", "c"])
        cfg = self._make_bench_cfg([sw])
        job = self._make_job(cfg, {"label": "a"})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_enum_values(self):
        sw = bn.EnumSweep(Color)
        cfg = self._make_bench_cfg([sw])
        job = self._make_job(cfg, {"color": Color.RED})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_bool_values(self):
        sw = bn.BoolSweep()
        cfg = self._make_bench_cfg([sw])
        job = self._make_job(cfg, {"flag": True})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_int_values(self):
        sw = bn.IntSweep(default=5, bounds=(0, 10))
        cfg = self._make_bench_cfg([sw])
        job = self._make_job(cfg, {"count": 5})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_float_values(self):
        sw = bn.FloatSweep(default=0.5, bounds=(0, 1), samples=5)
        cfg = self._make_bench_cfg([sw])
        job = self._make_job(cfg, {"ratio": 0.5})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_mutated_input_vars_in_bench_cfg(self):
        """BenchCfg containing with_level'd sweeps must pickle inside a Job."""
        input_vars = [
            bn.StringSweep(["a", "b", "c"]).with_level(3),
            bn.EnumSweep(Color).with_level(2),
            bn.BoolSweep().with_level(2),
            bn.IntSweep(default=0, bounds=(0, 10)).with_level(3),
            bn.FloatSweep(default=0.5, bounds=(0, 1), samples=5).with_level(3),
        ]
        cfg = self._make_bench_cfg(input_vars)
        job = self._make_job(cfg, {"label": "a", "color": Color.RED, "flag": True})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_const_vars(self):
        """BenchCfg with const_vars must pickle."""
        sw = bn.FloatSweep(default=0.5, bounds=(0, 1), samples=5)
        const_sw = bn.StringSweep(["x", "y", "z"])
        cfg = self._make_bench_cfg([sw], const_vars=[(const_sw, "y")])
        job = self._make_job(cfg, {"ratio": 0.5})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)

    def test_job_with_const_vars_after_with_level(self):
        """const_vars containing with_level'd sweeps must pickle."""
        sw = bn.FloatSweep(default=0.5, bounds=(0, 1), samples=5)
        const_sw = bn.StringSweep(["a", "b", "c"]).with_level(2)
        cfg = self._make_bench_cfg([sw], const_vars=[(const_sw, "a")])
        job = self._make_job(cfg, {"ratio": 0.5})
        restored = pickle.loads(pickle.dumps(job))
        assert run_job(restored) == run_job(job)


# ---------------------------------------------------------------------------
# 2. Job round-trip via ProcessPoolExecutor (actual multiprocessing)
# ---------------------------------------------------------------------------


class TestJobMultiprocessing:
    """Jobs must execute correctly when sent through ProcessPoolExecutor."""

    def _submit_job(self, job):
        payload = pickle.dumps(job, protocol=pickle.HIGHEST_PROTOCOL)
        with ProcessPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_job_in_subprocess, payload)
            return future.result(timeout=30)

    def _make_job_with_cfg(self, input_vars, job_args):
        cfg = BenchCfg(
            input_vars=input_vars,
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        return Job(job_id="mp:1", function=worker, job_args=job_args)

    def test_string_sweep_values_in_subprocess(self):
        job = self._make_job_with_cfg(
            [bn.StringSweep(["a", "b"]).with_level(2)],
            {"label": "a"},
        )
        result = self._submit_job(job)
        assert result == run_job(job)

    def test_enum_sweep_values_in_subprocess(self):
        job = self._make_job_with_cfg(
            [bn.EnumSweep(Color).with_level(2)],
            {"color": Color.GREEN},
        )
        result = self._submit_job(job)
        assert result == run_job(job)

    def test_bool_sweep_values_in_subprocess(self):
        job = self._make_job_with_cfg(
            [bn.BoolSweep().with_level(2)],
            {"flag": False},
        )
        result = self._submit_job(job)
        assert result == run_job(job)

    def test_mixed_sweep_types_in_subprocess(self):
        """All sweep types together in one Job, sent to subprocess."""
        input_vars = [
            bn.StringSweep(["x", "y", "z"]).with_level(2),
            bn.EnumSweep(Color).with_level(2),
            bn.BoolSweep().with_level(2),
            bn.IntSweep(default=0, bounds=(0, 5)).with_level(2),
            bn.FloatSweep(default=0.0, bounds=(0, 1), samples=3).with_level(2),
        ]
        job = self._make_job_with_cfg(
            input_vars,
            {"label": "x", "color": Color.RED, "flag": True, "count": 3, "ratio": 0.5},
        )
        result = self._submit_job(job)
        assert result == run_job(job)

    def test_many_string_values_in_subprocess(self):
        """Large number of string values — tests ListProxy edge cases."""
        strings = [f"val_{i}" for i in range(50)]
        sw = bn.StringSweep(strings).with_level(5)
        job = self._make_job_with_cfg([sw], {"label": "val_0"})
        result = self._submit_job(job)
        assert result == run_job(job)


# ---------------------------------------------------------------------------
# 3. WorkerJob hash + pickle (the dataclass sent alongside the Job)
# ---------------------------------------------------------------------------


class TestWorkerJobPickle:
    """WorkerJob dataclass must be picklable with all value types."""

    def _make_worker_job(self, dims_name, function_input_vars, constant_inputs=None):
        job = WorkerJob(
            function_input_vars=function_input_vars,
            index_tuple=tuple(range(len(function_input_vars))),
            dims_name=dims_name,
            constant_inputs=constant_inputs or {},
            bench_cfg_sample_hash="abc123",
            tag="test",
        )
        job.setup_hashes()
        return job

    def test_worker_job_with_string_values(self):
        job = self._make_worker_job(["label"], ["hello"])
        restored = pickle.loads(pickle.dumps(job))
        assert restored.function_input == job.function_input

    def test_worker_job_with_enum_values(self):
        job = self._make_worker_job(["color"], [Color.RED])
        restored = pickle.loads(pickle.dumps(job))
        assert restored.function_input == job.function_input

    def test_worker_job_with_bool_values(self):
        job = self._make_worker_job(["flag"], [True])
        restored = pickle.loads(pickle.dumps(job))
        assert restored.function_input == job.function_input

    def test_worker_job_with_mixed_values(self):
        job = self._make_worker_job(
            ["color", "label", "flag", "count"],
            [Color.BLUE, "fast", False, 7],
        )
        restored = pickle.loads(pickle.dumps(job))
        assert restored.function_input == job.function_input

    def test_worker_job_with_constant_inputs(self):
        job = self._make_worker_job(
            ["color"],
            [Color.RED],
            constant_inputs={"label": "fixed", "count": 5},
        )
        restored = pickle.loads(pickle.dumps(job))
        assert restored.function_input == job.function_input

    def test_worker_job_hash_deterministic(self):
        """Same inputs must produce the same hash."""
        job1 = self._make_worker_job(["color", "n"], [Color.RED, 5])
        job2 = self._make_worker_job(["color", "n"], [Color.RED, 5])
        assert job1.function_input_signature_pure == job2.function_input_signature_pure

    def test_worker_job_hash_differs_for_different_values(self):
        job1 = self._make_worker_job(["color"], [Color.RED])
        job2 = self._make_worker_job(["color"], [Color.BLUE])
        assert job1.function_input_signature_pure != job2.function_input_signature_pure


# ---------------------------------------------------------------------------
# 4. BenchCfg pickle with various input_var states
# ---------------------------------------------------------------------------


class TestBenchCfgPickle:
    """BenchCfg is captured by the partial and must survive pickle."""

    def _make_cfg(self, input_vars, const_vars=None):
        return BenchCfg(
            input_vars=input_vars,
            result_vars=[],
            const_vars=const_vars or [],
            bench_name="pickle_test",
            title="Pickle Test",
            pass_repeat=False,
        )

    def test_bench_cfg_with_raw_sweeps(self):
        cfg = self._make_cfg(
            [
                bn.StringSweep(["a", "b"]),
                bn.EnumSweep(Color),
                bn.BoolSweep(),
                bn.IntSweep(default=0, bounds=(0, 5)),
                bn.FloatSweep(default=0.0, bounds=(0, 1), samples=3),
            ]
        )
        restored = pickle.loads(pickle.dumps(cfg))
        for orig, rest in zip(cfg.input_vars, restored.input_vars):
            assert str(orig.values()) == str(rest.values())

    def test_bench_cfg_with_leveled_sweeps(self):
        """The exact scenario from PR #854."""
        cfg = self._make_cfg(
            [
                bn.StringSweep(["a", "b", "c"]).with_level(3),
                bn.EnumSweep(Color).with_level(2),
                bn.BoolSweep().with_level(2),
            ]
        )
        restored = pickle.loads(pickle.dumps(cfg))
        for orig, rest in zip(cfg.input_vars, restored.input_vars):
            assert rest.values() == orig.values()

    def test_bench_cfg_with_sampled_sweeps(self):
        cfg = self._make_cfg(
            [
                bn.StringSweep(["a", "b", "c", "d"]).with_samples(2),
                bn.EnumSweep(Algorithm).with_samples(2),
            ]
        )
        restored = pickle.loads(pickle.dumps(cfg))
        for orig, rest in zip(cfg.input_vars, restored.input_vars):
            assert rest.values() == orig.values()

    def test_bench_cfg_with_explicit_sample_values(self):
        cfg = self._make_cfg(
            [
                bn.StringSweep(["a", "b", "c"]).with_sample_values(["a", "c"]),
                bn.EnumSweep(Color).with_sample_values([Color.RED]),
            ]
        )
        restored = pickle.loads(pickle.dumps(cfg))
        for orig, rest in zip(cfg.input_vars, restored.input_vars):
            assert rest.values() == orig.values()

    def test_bench_cfg_with_const_vars_containing_selectors(self):
        sw = bn.StringSweep(["a", "b", "c"]).with_level(2)
        cfg = self._make_cfg(
            [bn.FloatSweep(default=0, bounds=(0, 1), samples=3)],
            const_vars=[(sw, "a")],
        )
        restored = pickle.loads(pickle.dumps(cfg))
        assert restored.const_vars[0][1] == "a"


# ---------------------------------------------------------------------------
# 5. worker_kwargs_wrapper pickle (the partial itself)
# ---------------------------------------------------------------------------


class TestWorkerWrapperPickle:
    """partial(worker_kwargs_wrapper, worker, bench_cfg) must be picklable."""

    def test_partial_with_module_function(self):
        cfg = BenchCfg(
            input_vars=[bn.StringSweep(["a", "b"]).with_level(2)],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        p = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        restored = pickle.loads(pickle.dumps(p))
        assert restored(label="a") == p(label="a")

    def test_partial_with_parametrized_sweep_call(self):
        """ParametrizedSweep.__call__ as worker must be picklable."""
        instance = StringOnlyConfig()
        cfg = BenchCfg(
            input_vars=[StringOnlyConfig.param.algorithm.with_level(3)],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        p = partial(worker_kwargs_wrapper, instance.__call__, cfg)
        restored = pickle.loads(pickle.dumps(p))
        result_orig = p(algorithm="quick")
        result_restored = restored(algorithm="quick")
        assert result_orig == result_restored

    def test_partial_filters_meta_vars_after_pickle(self):
        """After unpickling, meta vars must still be filtered."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

        # Need a module-level function for pickle, so we test via Job
        p = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        # Can't directly test meta filtering after pickle with lambda,
        # but we verify the partial roundtrips and the worker runs
        restored = pickle.loads(pickle.dumps(p))
        result = restored(label="test", over_time="2024-01-01", time_event="ev1")
        assert "result" in result


# ---------------------------------------------------------------------------
# 6. FutureCache with MULTIPROCESSING executor
# ---------------------------------------------------------------------------


class TestFutureCacheMultiprocessing:
    """FutureCache must correctly submit and retrieve results via multiprocessing."""

    def test_submit_and_retrieve(self):
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=True,
            cache_results=False,
        )
        cfg = BenchCfg(
            input_vars=[bn.StringSweep(["a", "b"]).with_level(2)],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        job = Job(job_id="fc:1", function=worker, job_args={"label": "a"})
        future = cache.submit(job)
        result = future.result()
        assert "result" in result
        cache.close()

    def test_submit_multiple_jobs(self):
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=True,
            cache_results=False,
        )
        cfg = BenchCfg(
            input_vars=[bn.EnumSweep(Color).with_level(2)],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        futures = []
        for i, color in enumerate([Color.RED, Color.GREEN, Color.BLUE]):
            job = Job(job_id=f"fc:{i}", function=worker, job_args={"color": color})
            futures.append(cache.submit(job))

        results = [f.result() for f in futures]
        assert len(results) == 3
        assert all("result" in r for r in results)
        cache.close()

    def test_submit_with_with_level_sweep_in_cfg(self):
        """The BenchCfg inside the partial has with_level'd sweeps."""
        cache = FutureCache(
            executor=Executors.MULTIPROCESSING,
            overwrite=True,
            cache_results=False,
        )
        input_vars = [
            bn.StringSweep(["x", "y", "z"]).with_level(3),
            bn.EnumSweep(Color).with_level(2),
            bn.BoolSweep().with_level(2),
        ]
        cfg = BenchCfg(
            input_vars=input_vars,
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        job = Job(
            job_id="fc:level",
            function=worker,
            job_args={"label": "x", "color": Color.RED, "flag": True},
        )
        future = cache.submit(job)
        result = future.result()
        assert "result" in result
        cache.close()


# ---------------------------------------------------------------------------
# 7. End-to-end: Bench.plot_sweep with MULTIPROCESSING
# ---------------------------------------------------------------------------


class TestBenchMultiprocessingEndToEnd:
    """Full Bench.plot_sweep execution with MULTIPROCESSING executor.

    These tests exercise the complete pipeline:
    ParametrizedSweep → Bench → WorkerJob → Job → ProcessPoolExecutor →
    run_job → worker_kwargs_wrapper → worker → results
    """

    def _run_bench(self, worker_instance, input_vars):
        bench = bn.Bench("mp_test", worker_instance)
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = Executors.MULTIPROCESSING
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        res = bench.plot_sweep(
            "mp_sweep",
            input_vars=input_vars,
            run_cfg=run_cfg,
            plot_callbacks=False,
        )
        return res

    def test_string_sweep_multiprocessing(self):
        """StringSweep — the primary type affected by PR #854."""
        worker = StringOnlyConfig()
        res = self._run_bench(
            worker,
            [StringOnlyConfig.param.algorithm.with_level(3)],
        )
        assert res.result_samples() > 0

    def test_enum_sweep_multiprocessing(self):
        worker = EnumOnlyConfig()
        res = self._run_bench(
            worker,
            [EnumOnlyConfig.param.algo.with_level(3)],
        )
        assert res.result_samples() > 0

    def test_bool_sweep_multiprocessing(self):
        worker = BoolOnlyConfig()
        res = self._run_bench(
            worker,
            [BoolOnlyConfig.param.flag.with_level(2)],
        )
        assert res.result_samples() > 0

    def test_mixed_selector_and_numeric_multiprocessing(self):
        """All selector types + numeric in one sweep."""
        worker = MixedSelectorConfig()
        res = self._run_bench(
            worker,
            [
                MixedSelectorConfig.param.color.with_level(2),
                MixedSelectorConfig.param.label.with_level(2),
                MixedSelectorConfig.param.active.with_level(2),
                MixedSelectorConfig.param.weight.with_level(2),
            ],
        )
        assert res.result_samples() > 0

    def test_multi_type_config_multiprocessing(self):
        """All sweep types together."""
        worker = MultiTypeConfig()
        res = self._run_bench(
            worker,
            [
                MultiTypeConfig.param.color.with_level(2),
                MultiTypeConfig.param.label.with_level(2),
                MultiTypeConfig.param.count.with_level(2),
            ],
        )
        assert res.result_samples() > 0

    def test_with_samples_multiprocessing(self):
        """with_samples (not with_level) under multiprocessing."""
        worker = StringOnlyConfig()
        res = self._run_bench(
            worker,
            [StringOnlyConfig.param.algorithm.with_samples(3)],
        )
        assert res.result_samples() > 0

    def test_with_sample_values_multiprocessing(self):
        """Explicit sample values under multiprocessing."""
        worker = EnumOnlyConfig()
        res = self._run_bench(
            worker,
            [EnumOnlyConfig.param.algo.with_sample_values([Algorithm.QUICK, Algorithm.HEAP])],
        )
        assert res.result_samples() == 2

    def test_multiprocessing_with_repeats(self):
        """Multiple repeats under multiprocessing."""
        worker = StringOnlyConfig()
        bench = bn.Bench("mp_repeat_test", worker)
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = Executors.MULTIPROCESSING
        run_cfg.repeats = 3
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        res = bench.plot_sweep(
            "mp_repeat_sweep",
            input_vars=[StringOnlyConfig.param.algorithm.with_level(2)],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )
        # 2 algorithms * 3 repeats = 6 samples
        assert res.result_samples() == 6

    def test_multiprocessing_with_const_vars(self):
        """Constant variables under multiprocessing."""
        worker = MixedSelectorConfig()
        bench = bn.Bench("mp_const_test", worker)
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = Executors.MULTIPROCESSING
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        res = bench.plot_sweep(
            "mp_const_sweep",
            input_vars=[MixedSelectorConfig.param.weight.with_level(3)],
            const_vars=[
                MixedSelectorConfig.param.color.with_const(Color.RED),
                MixedSelectorConfig.param.label.with_const("x"),
                MixedSelectorConfig.param.active.with_const(True),
            ],
            run_cfg=run_cfg,
            plot_callbacks=False,
        )
        assert res.result_samples() > 0


# ---------------------------------------------------------------------------
# 8. BenchRunner with MULTIPROCESSING
# ---------------------------------------------------------------------------


class TestBenchRunnerMultiprocessing:
    """BenchRunner end-to-end with MULTIPROCESSING executor."""

    def test_bench_runner_string_sweep(self):
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = Executors.MULTIPROCESSING
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        bench_run = bn.BenchRunner("mp_runner_test", run_cfg=run_cfg)
        bench_run.add_bench(StringOnlyConfig())
        bench_run.run(level=2)

    def test_bench_runner_multi_type(self):
        run_cfg = bn.BenchRunCfg()
        run_cfg.executor = Executors.MULTIPROCESSING
        run_cfg.overwrite_sample_cache = True
        run_cfg.cache_samples = False
        run_cfg.print_bench_inputs = False
        run_cfg.print_bench_results = False
        bench_run = bn.BenchRunner("mp_runner_multi_test", run_cfg=run_cfg)
        bench_run.add_bench(MultiTypeConfig())
        bench_run.run(level=2)


# ---------------------------------------------------------------------------
# 9. Deepcopy safety of BenchCfg (used extensively before multiprocessing)
# ---------------------------------------------------------------------------


class TestBenchCfgDeepcopy:
    """BenchCfg is deepcopied multiple times before being captured in a partial."""

    def test_deepcopy_preserves_values(self):
        cfg = BenchCfg(
            input_vars=[
                bn.StringSweep(["a", "b", "c"]).with_level(3),
                bn.EnumSweep(Color).with_level(2),
                bn.BoolSweep().with_level(2),
            ],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
        )
        cloned = deepcopy(cfg)
        for orig, clone in zip(cfg.input_vars, cloned.input_vars):
            assert clone.values() == orig.values()

    def test_deepcopy_then_pickle(self):
        cfg = BenchCfg(
            input_vars=[
                bn.StringSweep(["a", "b"]).with_level(2),
                bn.EnumSweep(Color).with_level(2),
            ],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
        )
        cloned = deepcopy(cfg)
        restored = pickle.loads(pickle.dumps(cloned))
        for orig, rest in zip(cfg.input_vars, restored.input_vars):
            assert rest.values() == orig.values()

    def test_multiple_deepcopies(self):
        """Simulates the chain of deepcopies that happens in real execution."""
        sw = bn.StringSweep(["a", "b", "c"]).with_level(3)
        copy1 = deepcopy(sw)
        copy2 = deepcopy(copy1)
        copy3 = deepcopy(copy2)
        restored = pickle.loads(pickle.dumps(copy3))
        assert restored.values() == sw.values()


# ---------------------------------------------------------------------------
# 10. Edge cases: empty sweeps, single-element, large sweeps
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases that could break multiprocessing serialization."""

    def test_single_value_string_sweep(self):
        sw = bn.StringSweep(["only_one"])
        mutated = sw.with_level(1)
        data = pickle.dumps(mutated)
        restored = pickle.loads(data)
        assert restored.values() == ["only_one"]

    def test_single_value_enum_sweep(self):
        sw = bn.EnumSweep([Color.RED])
        mutated = sw.with_level(1)
        data = pickle.dumps(mutated)
        restored = pickle.loads(data)
        assert restored.values() == [Color.RED]

    def test_large_string_sweep(self):
        """Large number of values should not cause issues."""
        strings = [f"item_{i:04d}" for i in range(200)]
        sw = bn.StringSweep(strings).with_level(6)
        data = pickle.dumps(sw)
        restored = pickle.loads(data)
        assert restored.values() == sw.values()

    def test_string_sweep_with_special_characters(self):
        sw = bn.StringSweep(["hello world", "foo/bar", "baz\\qux", "a=b&c=d"])
        mutated = sw.with_level(3)
        data = pickle.dumps(mutated)
        restored = pickle.loads(data)
        assert restored.values() == mutated.values()

    def test_job_args_with_none_value(self):
        """None values in job_args must survive pickle."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        job = Job(job_id="edge:1", function=worker, job_args={"x": None})
        restored = pickle.loads(pickle.dumps(job))
        assert restored.job_args == {"x": None}

    def test_job_args_with_nested_mutable(self):
        """Mutable values in job_args must survive pickle without corruption."""
        cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
        )
        worker = partial(worker_kwargs_wrapper, _simple_worker, cfg)
        job = Job(job_id="edge:2", function=worker, job_args={"data": [1, 2, 3]})
        restored = pickle.loads(pickle.dumps(job))
        assert restored.job_args["data"] == [1, 2, 3]
