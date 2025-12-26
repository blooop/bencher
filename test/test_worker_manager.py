"""Tests for WorkerManager extracted from Bench."""

import unittest
from hypothesis import given, settings, strategies as st

from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.worker_manager import WorkerManager, worker_cfg_wrapper, kwargs_to_input_cfg


class TestWorkerManager(unittest.TestCase):
    """Tests for WorkerManager extracted from Bench."""

    def setUp(self):
        self.manager = WorkerManager()

    def test_set_worker_from_parametrized_sweep(self):
        """Test setting worker from ParametrizedSweep instance."""
        instance = ExampleBenchCfg()
        self.manager.set_worker(instance)
        self.assertEqual(self.manager.worker, instance.__call__)
        self.assertEqual(self.manager.worker_class_instance, instance)

    def test_set_worker_from_callable(self):
        """Test setting worker from function."""

        def my_worker(**_kwargs):
            return {"result": 1}

        self.manager.set_worker(my_worker)
        self.assertEqual(self.manager.worker, my_worker)
        self.assertIsNone(self.manager.worker_class_instance)

    def test_set_worker_with_input_cfg(self):
        """Test setting worker with separate config."""

        def my_worker(cfg):
            return {"result": cfg.theta}

        self.manager.set_worker(my_worker, ExampleBenchCfg)
        # Worker should be wrapped with config - it's now a partial
        self.assertIsNotNone(self.manager.worker)
        self.assertEqual(self.manager.worker_input_cfg, ExampleBenchCfg)

    def test_set_worker_class_type_error(self):
        """Test error when class type passed instead of instance."""
        with self.assertRaises(RuntimeError):
            self.manager.set_worker(ExampleBenchCfg)  # Class, not instance

    def test_get_result_vars_as_str(self):
        """Test getting result var names as strings."""
        self.manager.set_worker(ExampleBenchCfg())
        result_vars = self.manager.get_result_vars(as_str=True)
        self.assertIsInstance(result_vars[0], str)
        self.assertIn("out_sin", result_vars)

    def test_get_result_vars_as_params(self):
        """Test getting result vars as Parameter objects."""
        self.manager.set_worker(ExampleBenchCfg())
        result_vars = self.manager.get_result_vars(as_str=False)
        self.assertTrue(hasattr(result_vars[0], "name"))

    def test_get_result_vars_no_instance_error(self):
        """Test error when worker instance not set."""
        with self.assertRaises(RuntimeError):
            self.manager.get_result_vars()

    def test_get_inputs_only(self):
        """Test getting input variables."""
        self.manager.set_worker(ExampleBenchCfg())
        inputs = self.manager.get_inputs_only()
        self.assertIsInstance(inputs, list)
        self.assertGreater(len(inputs), 0)

    def test_get_inputs_only_no_instance_error(self):
        """Test error when worker instance not set for get_inputs_only."""
        with self.assertRaises(RuntimeError):
            self.manager.get_inputs_only()

    def test_get_input_defaults(self):
        """Test getting default input values."""
        self.manager.set_worker(ExampleBenchCfg())
        defaults = self.manager.get_input_defaults()
        self.assertIsInstance(defaults, list)

    def test_get_input_defaults_no_instance_error(self):
        """Test error when worker instance not set for get_input_defaults."""
        with self.assertRaises(RuntimeError):
            self.manager.get_input_defaults()

    # Hypothesis property-based tests
    @settings(deadline=10000)
    @given(as_str=st.booleans())
    def test_get_result_vars_return_type(self, as_str):
        """Property: return type matches as_str parameter."""
        self.manager.set_worker(ExampleBenchCfg())
        result_vars = self.manager.get_result_vars(as_str=as_str)
        if as_str:
            self.assertTrue(all(isinstance(v, str) for v in result_vars))
        else:
            self.assertTrue(all(hasattr(v, "name") for v in result_vars))


class TestKwargsToInputCfg(unittest.TestCase):
    """Tests for kwargs_to_input_cfg function."""

    def test_creates_instance(self):
        """Test that it creates an instance of the config class."""
        cfg = kwargs_to_input_cfg(ExampleBenchCfg)
        self.assertIsInstance(cfg, ExampleBenchCfg)

    def test_updates_with_kwargs(self):
        """Test that kwargs are applied to the config."""
        cfg = kwargs_to_input_cfg(ExampleBenchCfg, theta=1.5)
        self.assertEqual(cfg.theta, 1.5)


class TestWorkerCfgWrapper(unittest.TestCase):
    """Tests for worker_cfg_wrapper function."""

    def test_wrapper_calls_worker_with_config(self):
        """Test wrapper creates config instance correctly."""
        call_log = []

        def my_worker(cfg):
            call_log.append(cfg)
            return {"result": cfg.theta}

        result = worker_cfg_wrapper(my_worker, ExampleBenchCfg, theta=2.0)

        self.assertEqual(len(call_log), 1)
        self.assertIsInstance(call_log[0], ExampleBenchCfg)
        self.assertEqual(call_log[0].theta, 2.0)
        self.assertEqual(result, {"result": 2.0})


if __name__ == "__main__":
    unittest.main()
