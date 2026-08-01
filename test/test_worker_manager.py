"""Tests for WorkerManager extracted from Bench."""

import dataclasses
import unittest
from typing import get_args

from hypothesis import given, settings
from hypothesis import strategies as st

from bencher.example.benchmark_data import ExampleBenchCfg
from bencher.worker_manager import (
    Declared,
    RunnableFunction,
    RunnableInstance,
    Unbound,
    WorkerManager,
    WorkerState,
    kwargs_to_input_cfg,
    worker_cfg_wrapper,
)


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

    def test_set_worker_class_attaches_the_class_without_a_callable_worker(self):
        """The declaration-only path used by sweep_identity.

        ``worker`` stays None on purpose: a class cannot be called, so leaving it unset
        makes an attempt to sample fail loudly rather than call a class object.
        """
        self.manager.set_worker_class(ExampleBenchCfg)
        self.assertIs(self.manager.worker_class_instance, ExampleBenchCfg)
        self.assertIsNone(self.manager.worker)
        # A class is enough to answer what the declaration is made of.
        self.assertIn("out_sin", self.manager.get_result_vars(as_str=True))

    def test_set_worker_class_rejects_an_instance(self):
        """The mirror of set_worker's complaint, so neither silently takes the other's."""
        with self.assertRaises(RuntimeError):
            self.manager.set_worker_class(ExampleBenchCfg())

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


class TestWorkerState(unittest.TestCase):
    """The WorkerState sum type and every transition between its variants (plan 23 P9).

    Before P9 the same information lived in one
    ``worker_class_instance: ParametrizedSweep | type[ParametrizedSweep] | None`` field
    with "declaration only" inferred from ``worker is None``, so "callable" and "declares
    the sweep's variables" could not be told apart by type. These tests pin each of the
    four states, the ``worker`` / ``worker_class_instance`` views over them, and that a
    rejected call leaves the previous state untouched.
    """

    def setUp(self):
        self.manager = WorkerManager()

    def test_a_fresh_manager_is_unbound(self):
        """Nothing attached is its own state, not a pair of Nones."""
        self.assertEqual(self.manager.state, Unbound())
        self.assertIsNone(self.manager.worker)
        self.assertIsNone(self.manager.worker_class_instance)

    def test_unbound_to_runnable_instance(self):
        """set_worker(instance): callable *and* the declaration source."""
        instance = ExampleBenchCfg()
        self.manager.set_worker(instance)
        self.assertEqual(self.manager.state, RunnableInstance(instance))
        self.assertEqual(self.manager.worker, instance.__call__)
        self.assertIs(self.manager.worker_class_instance, instance)

    def test_unbound_to_runnable_function(self):
        """set_worker(fn): callable, but nothing declares the sweep's variables."""

        def my_worker(**_kwargs):
            return {"result": 1}

        self.manager.set_worker(my_worker)
        self.assertEqual(self.manager.state, RunnableFunction(my_worker))
        self.assertIs(self.manager.worker, my_worker)
        self.assertIsNone(self.manager.worker_class_instance)

    def test_unbound_to_runnable_function_with_input_cfg(self):
        """The config class is folded into the callable, not kept as a second mode."""

        def my_worker(cfg):
            return {"result": cfg.theta}

        self.manager.set_worker(my_worker, ExampleBenchCfg)
        self.assertIsInstance(self.manager.state, RunnableFunction)
        self.assertIsNot(self.manager.worker, my_worker)  # wrapped in a partial
        self.assertIs(self.manager.worker_input_cfg, ExampleBenchCfg)
        # A config class is still not a declaration source: it never was one, and
        # promoting it would switch on plot_sweep's auto-discovery for these callers.
        self.assertIsNone(self.manager.worker_class_instance)

    def test_unbound_to_declared(self):
        """set_worker_class(cls): declares the sweep but cannot be sampled."""
        self.manager.set_worker_class(ExampleBenchCfg)
        self.assertEqual(self.manager.state, Declared(ExampleBenchCfg))
        self.assertIsNone(self.manager.worker)
        self.assertIs(self.manager.worker_class_instance, ExampleBenchCfg)

    def test_declared_to_runnable_instance(self):
        """Declaring first and binding later (sweep_identity then a real run)."""
        self.manager.set_worker_class(ExampleBenchCfg)
        instance = ExampleBenchCfg()
        self.manager.set_worker(instance)
        self.assertEqual(self.manager.state, RunnableInstance(instance))
        self.assertEqual(self.manager.worker, instance.__call__)

    def test_runnable_instance_to_declared(self):
        """Redeclaring drops the callable rather than leaving a stale one behind."""
        self.manager.set_worker(ExampleBenchCfg())
        self.manager.set_worker_class(ExampleBenchCfg)
        self.assertEqual(self.manager.state, Declared(ExampleBenchCfg))
        self.assertIsNone(self.manager.worker)

    def test_runnable_function_to_runnable_instance(self):
        """Rebinding a function manager to an instance makes it declaring too."""

        def my_worker(**_kwargs):
            return {"result": 1}

        self.manager.set_worker(my_worker)
        instance = ExampleBenchCfg()
        self.manager.set_worker(instance)
        self.assertEqual(self.manager.state, RunnableInstance(instance))
        self.assertIs(self.manager.worker_class_instance, instance)

    def test_a_rejected_class_leaves_the_state_untouched(self):
        """set_worker(cls) raises without half-binding anything."""
        instance = ExampleBenchCfg()
        self.manager.set_worker(instance)
        with self.assertRaises(RuntimeError):
            self.manager.set_worker(ExampleBenchCfg)
        self.assertEqual(self.manager.state, RunnableInstance(instance))

    def test_a_rejected_instance_leaves_the_state_untouched(self):
        """set_worker_class(instance) raises without half-declaring anything."""
        self.manager.set_worker_class(ExampleBenchCfg)
        with self.assertRaises(RuntimeError):
            self.manager.set_worker_class(ExampleBenchCfg())
        self.assertEqual(self.manager.state, Declared(ExampleBenchCfg))

    def test_states_are_frozen(self):
        """A state is a value: it is replaced by set_worker*, never mutated in place."""
        self.manager.set_worker_class(ExampleBenchCfg)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            self.manager.state.worker_class = ExampleBenchCfg  # type: ignore[misc]

    def test_the_union_has_exactly_the_four_documented_variants(self):
        """Guards the union against a variant added without updating the matches."""
        self.assertEqual(
            set(get_args(WorkerState)),
            {Unbound, Declared, RunnableFunction, RunnableInstance},
        )

    def test_unbound_variable_reads_name_what_to_call(self):
        """Setup-time failure, so raising is right -- but the message must be actionable."""
        for read in (
            self.manager.get_result_vars,
            self.manager.get_inputs_only,
            self.manager.get_input_defaults,
        ):
            with self.subTest(read=read.__name__), self.assertRaises(RuntimeError) as ctx:
                read()
            message = str(ctx.exception)
            self.assertIn("set_worker(", message)
            self.assertIn("set_worker_class(", message)

    def test_plain_function_variable_reads_say_why_and_what_to_pass(self):
        """A function worker has no declaration source; the message says so by name."""

        def my_worker(**_kwargs):
            return {"result": 1}

        self.manager.set_worker(my_worker)
        for read in (
            self.manager.get_result_vars,
            self.manager.get_inputs_only,
            self.manager.get_input_defaults,
        ):
            with self.subTest(read=read.__name__), self.assertRaises(RuntimeError) as ctx:
                read()
            message = str(ctx.exception)
            self.assertIn("plain function", message)
            self.assertIn("set_worker(", message)
            self.assertIn("result_vars", message)

    def test_declared_answers_every_variable_read(self):
        """A class is enough to describe a sweep -- the reason Declared exists."""
        self.manager.set_worker_class(ExampleBenchCfg)
        self.assertIn("out_sin", self.manager.get_result_vars(as_str=True))
        self.assertTrue(self.manager.get_inputs_only())
        self.assertIsInstance(self.manager.get_input_defaults(), list)

    def test_state_is_read_only(self):
        """Only set_worker* may change the state; nothing may poke it directly."""
        with self.assertRaises(AttributeError):
            self.manager.state = Unbound()


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
