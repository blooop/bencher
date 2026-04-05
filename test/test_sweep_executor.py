"""Tests for SweepExecutor extracted from Bench."""

import unittest

from hypothesis import given, settings, strategies as st

from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.sweep_executor import SweepExecutor, worker_kwargs_wrapper
from bencher.bench_cfg import BenchCfg, BenchRunCfg
from bencher.job import Executors


class TestSweepExecutor(unittest.TestCase):
    """Tests for SweepExecutor extracted from Bench."""

    def setUp(self):
        self.executor = SweepExecutor()
        self.worker_instance = ExampleBenchCfg()

    def test_init_default_cache_size(self):
        """Test default cache size is set."""
        executor = SweepExecutor()
        self.assertEqual(executor.cache_size, int(100e9))

    def test_init_custom_cache_size(self):
        """Test custom cache size is set."""
        executor = SweepExecutor(cache_size=int(50e9))
        self.assertEqual(executor.cache_size, int(50e9))

    def test_convert_vars_to_params_from_string(self):
        """Test converting string variable names to params."""
        result = self.executor.convert_vars_to_params(
            "theta",
            "input",
            None,
            worker_class_instance=self.worker_instance,
            worker_input_cfg=ExampleBenchCfg,
        )
        self.assertEqual(result.name, "theta")

    def test_convert_vars_to_params_from_dict(self):
        """Test converting dict config to params."""
        result = self.executor.convert_vars_to_params(
            {"name": "theta", "samples": 5},
            "input",
            None,
            worker_class_instance=self.worker_instance,
            worker_input_cfg=ExampleBenchCfg,
        )
        self.assertEqual(result.name, "theta")

    def test_convert_vars_to_params_from_param(self):
        """Test passing param.Parameter directly."""
        result = self.executor.convert_vars_to_params(
            self.worker_instance.param.theta,
            "input",
            None,
            worker_class_instance=self.worker_instance,
            worker_input_cfg=ExampleBenchCfg,
        )
        self.assertEqual(result.name, "theta")

    def test_convert_vars_to_params_type_error(self):
        """Test proper error for invalid variable types."""
        with self.assertRaises(TypeError):
            self.executor.convert_vars_to_params(
                12345,  # Invalid type
                "input",
                None,
                worker_class_instance=self.worker_instance,
                worker_input_cfg=ExampleBenchCfg,
            )

    def test_define_const_inputs(self):
        """Test converting const tuples to dict."""
        const_vars = [
            (self.worker_instance.param.theta, 1.5),
            (self.worker_instance.param.offset, 0.1),
        ]
        result = self.executor.define_const_inputs(const_vars)

        self.assertEqual(result["theta"], 1.5)
        self.assertEqual(result["offset"], 0.1)

    def test_define_const_inputs_none(self):
        """Test None input returns None."""
        result = self.executor.define_const_inputs(None)
        self.assertIsNone(result)

    def test_init_sample_cache(self):
        """Test FutureCache initialization with config."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = True
        run_cfg.executor = Executors.SERIAL

        cache = self.executor.init_sample_cache(run_cfg)

        self.assertIsNotNone(cache)
        self.assertEqual(self.executor.sample_cache, cache)

    def test_init_sample_cache_with_caching_disabled(self):
        """Test FutureCache when cache_samples=False."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = False
        run_cfg.executor = Executors.SERIAL

        cache = self.executor.init_sample_cache(run_cfg)

        self.assertIsNotNone(cache)
        # When cache_samples=False, cache.cache should be None
        self.assertIsNone(cache.cache)

    def test_clear_call_counts(self):
        """Test clearing call counts."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = True
        run_cfg.executor = Executors.SERIAL

        self.executor.init_sample_cache(run_cfg)
        self.executor.sample_cache.worker_wrapper_call_count = 5

        self.executor.clear_call_counts()

        self.assertEqual(self.executor.sample_cache.worker_wrapper_call_count, 0)

    def test_clear_call_counts_no_cache(self):
        """Test clearing call counts when no cache exists."""
        # Should not raise
        self.executor.clear_call_counts()

    def test_close_cache(self):
        """Test closing the cache."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = True
        run_cfg.executor = Executors.SERIAL

        self.executor.init_sample_cache(run_cfg)
        self.executor.close_cache()

    def test_close_cache_no_cache(self):
        """Test closing cache when none exists."""
        # Should not raise
        self.executor.close_cache()

    def test_get_cache_stats_no_cache(self):
        """Test getting stats when no cache exists."""
        result = self.executor.get_cache_stats()
        self.assertEqual(result, "")

    def test_get_cache_stats_with_cache(self):
        """Test getting stats when cache is present."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = True
        run_cfg.executor = Executors.SERIAL

        self.executor.init_sample_cache(run_cfg)
        result = self.executor.get_cache_stats()

        # Should return non-empty stats string
        self.assertIsInstance(result, str)

    def test_convert_vars_to_params_with_max_level(self):
        """Test max_level handling when run_cfg.level is set."""
        run_cfg = BenchRunCfg()
        run_cfg.level = 2

        result = self.executor.convert_vars_to_params(
            {"name": "theta", "max_level": 3},
            "input",
            run_cfg,
            worker_class_instance=self.worker_instance,
            worker_input_cfg=ExampleBenchCfg,
        )

        self.assertEqual(result.name, "theta")
        # The parameter should have been processed with level adjustment

    def test_convert_vars_to_params_bad_string_gives_helpful_error(self):
        """Test that a typo in a string variable name gives a helpful KeyError."""
        with self.assertRaises(KeyError) as ctx:
            self.executor.convert_vars_to_params(
                "thetaa",
                "input",
                None,
                worker_class_instance=self.worker_instance,
                worker_input_cfg=ExampleBenchCfg,
            )
        msg = str(ctx.exception)
        self.assertIn("thetaa", msg)
        self.assertIn("not found", msg)
        self.assertIn("Available parameters", msg)
        self.assertIn("theta", msg)  # listed in available parameters

    def test_convert_vars_to_params_bad_dict_name_gives_helpful_error(self):
        """Test that a typo in a dict variable name gives a helpful KeyError."""
        with self.assertRaises(KeyError) as ctx:
            self.executor.convert_vars_to_params(
                {"name": "thetaa"},
                "input",
                None,
                worker_class_instance=self.worker_instance,
                worker_input_cfg=ExampleBenchCfg,
            )
        msg = str(ctx.exception)
        self.assertIn("thetaa", msg)
        self.assertIn("not found", msg)

    def test_clear_tag_from_sample_cache_lazy_init(self):
        """Test clear_tag_from_sample_cache initializes cache if None."""
        # sample_cache should be None initially
        self.assertIsNone(self.executor.sample_cache)

        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = True
        run_cfg.executor = Executors.SERIAL

        # This should initialize the cache lazily
        self.executor.clear_tag_from_sample_cache("test_tag", run_cfg)

        # Cache should now be initialized
        self.assertIsNotNone(self.executor.sample_cache)

    # Hypothesis property-based tests
    @settings(deadline=10000)
    @given(
        cache_samples=st.booleans(),
    )
    def test_init_sample_cache_configs(self, cache_samples):
        """Property: cache initializes correctly with various configs."""
        run_cfg = BenchRunCfg()
        run_cfg.cache_samples = cache_samples
        run_cfg.executor = Executors.SERIAL

        cache = self.executor.init_sample_cache(run_cfg)

        self.assertIsNotNone(cache)
        if cache_samples:
            self.assertIsNotNone(cache.cache)
        else:
            self.assertIsNone(cache.cache)


class TestWorkerKwargsWrapper(unittest.TestCase):
    """Tests for worker_kwargs_wrapper function."""

    def test_filters_repeat_when_pass_repeat_false(self):
        """Test repeat is filtered when pass_repeat=False."""
        call_log = []

        def my_worker(**kwargs):
            call_log.append(kwargs)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

        worker_kwargs_wrapper(my_worker, bench_cfg, theta=1.0, repeat=1)

        self.assertNotIn("repeat", call_log[0])
        self.assertIn("theta", call_log[0])

    def test_passes_repeat_when_pass_repeat_true(self):
        """Test repeat is passed when pass_repeat=True."""
        call_log = []

        def my_worker(**kwargs):
            call_log.append(kwargs)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=True,
        )

        worker_kwargs_wrapper(my_worker, bench_cfg, theta=1.0, repeat=1)

        self.assertIn("repeat", call_log[0])
        self.assertIn("theta", call_log[0])

    def test_filters_meta_vars(self):
        """Test over_time and time_event are always filtered."""
        call_log = []

        def my_worker(**kwargs):
            call_log.append(kwargs)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=True,
        )

        worker_kwargs_wrapper(
            my_worker, bench_cfg, theta=1.0, repeat=1, over_time="2024-01-01", time_event="ev1"
        )

        self.assertNotIn("over_time", call_log[0])
        self.assertNotIn("time_event", call_log[0])
        self.assertIn("theta", call_log[0])

    def test_does_not_mutate_original_kwargs(self):
        """Verify that the original kwargs dict is not mutated by filtering."""

        def my_worker(**_kwargs):
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

        original = {"theta": 1.0, "repeat": 1, "over_time": "2024-01-01", "time_event": "ev1"}
        snapshot = dict(original)

        worker_kwargs_wrapper(my_worker, bench_cfg, **original)

        self.assertEqual(original, snapshot)

    def test_worker_mutation_of_mutable_value_does_not_leak(self):
        """Verify deepcopy prevents worker mutations of mutable values from leaking back."""
        shared_list = [1, 2, 3]

        def mutating_worker(**kwargs):
            kwargs["data"].append(999)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

        original = {"data": shared_list, "repeat": 1}
        worker_kwargs_wrapper(mutating_worker, bench_cfg, **original)

        self.assertEqual(shared_list, [1, 2, 3])

    def test_no_meta_keys_present(self):
        """Test behavior when no metadata keys are in kwargs."""
        call_log = []

        def my_worker(**kwargs):
            call_log.append(kwargs)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=True,
        )

        worker_kwargs_wrapper(my_worker, bench_cfg, theta=1.0, phi=2.0)

        self.assertEqual(call_log[0], {"theta": 1.0, "phi": 2.0})

    def test_only_meta_keys(self):
        """Test that worker receives empty dict when only metadata keys are present."""
        call_log = []

        def my_worker(**kwargs):
            call_log.append(kwargs)
            return {"result": 1}

        bench_cfg = BenchCfg(
            input_vars=[],
            result_vars=[],
            const_vars=[],
            bench_name="test",
            title="test",
            pass_repeat=False,
        )

        worker_kwargs_wrapper(my_worker, bench_cfg, repeat=1, over_time="t", time_event="e")

        self.assertEqual(call_log[0], {})


if __name__ == "__main__":
    unittest.main()
