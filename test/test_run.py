"""Tests for the bch.run() convenience function."""

import unittest
import warnings
import bencher as bch
from bencher.example.example_simple_float import SimpleFloat, example_simple_float


class TestRun(unittest.TestCase):
    """Tests for bch.run() covering all three target types and parameter propagation."""

    def test_run_callable(self):
        """bch.run() with a standard benchmark function."""
        results = bch.run(example_simple_float, show=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_run_parametrized_sweep_class(self):
        """bch.run() with a ParametrizedSweep class (not instance)."""
        results = bch.run(SimpleFloat, show=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_run_parametrized_sweep_instance(self):
        """bch.run() with a ParametrizedSweep instance."""
        results = bch.run(SimpleFloat(), show=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_run_callable_level_propagates(self):
        """bch.run() propagates level to the benchmark result for callables."""
        results = bch.run(example_simple_float, level=3, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.level, 3)

    def test_run_callable_repeats_propagates(self):
        """bch.run() propagates repeats to the benchmark result for callables."""
        results = bch.run(example_simple_float, level=2, repeats=3, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.repeats, 3)

    def test_run_sweep_class_level_propagates(self):
        """bch.run() propagates level to the benchmark result for ParametrizedSweep classes."""
        results = bch.run(SimpleFloat, level=3, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.level, 3)

    def test_run_sweep_class_repeats_propagates(self):
        """bch.run() propagates repeats to the benchmark result for ParametrizedSweep classes."""
        results = bch.run(SimpleFloat, level=2, repeats=2, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.repeats, 2)

    def test_run_sweep_instance_level_propagates(self):
        """bch.run() propagates level to the benchmark result for ParametrizedSweep instances."""
        results = bch.run(SimpleFloat(), level=3, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.level, 3)

    def test_run_sweep_instance_repeats_propagates(self):
        """bch.run() propagates repeats for ParametrizedSweep instances."""
        results = bch.run(SimpleFloat(), level=2, repeats=2, show=False)
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].last_run_cfg.repeats, 2)

    def test_run_with_explicit_run_cfg(self):
        """bch.run() respects an explicit BenchRunCfg."""
        cfg = bch.BenchRunCfg()
        cfg.repeats = 2
        results = bch.run(example_simple_float, run_cfg=cfg, show=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_run_with_save(self):
        """bch.run() with save=True doesn't crash."""
        results = bch.run(example_simple_float, show=False, save=True)
        self.assertIsInstance(results, list)

    def test_run_progressive_levels(self):
        """bch.run() with max_level produces results for each level."""
        results = bch.run(example_simple_float, level=2, max_level=3, show=False)
        self.assertEqual(len(results), 2)  # level 2 and level 3

    def test_run_progressive_repeats(self):
        """bch.run() with max_repeats produces results for each repeat count."""
        results = bch.run(example_simple_float, repeats=1, max_repeats=2, show=False)
        self.assertEqual(len(results), 2)  # repeats 1 and repeats 2

    def test_run_progressive_levels_and_repeats(self):
        """bch.run() with both max_level and max_repeats produces the cross product."""
        results = bch.run(
            example_simple_float, level=2, max_level=3, repeats=1, max_repeats=2, show=False
        )
        # 2 levels x 2 repeat counts = 4 results
        self.assertEqual(len(results), 4)

    def test_run_default_show_is_true(self):
        """Verify the default for show is True (documented API contract)."""
        import inspect

        sig = inspect.signature(bch.run)
        self.assertTrue(sig.parameters["show"].default)

    def test_run_returns_bench_objects(self):
        """bch.run() returns a list of Bench objects with last_run_cfg."""
        results = bch.run(example_simple_float, show=False)
        for r in results:
            self.assertTrue(hasattr(r, "last_run_cfg"))
            self.assertTrue(hasattr(r, "report"))


class TestAddRunDeprecation(unittest.TestCase):
    """Tests for the add_run() deprecation warning."""

    def test_add_run_emits_deprecation_warning(self):
        """add_run() emits a DeprecationWarning."""
        bench_runner = bch.BenchRunner("test_deprecation")
        bench_fn = lambda run_cfg: None  # noqa: E731
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bench_runner.add_run(bench_fn)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            self.assertEqual(len(deprecation_warnings), 1)
            self.assertIn("add_run() is deprecated", str(deprecation_warnings[0].message))

    def test_add_run_still_adds_function(self):
        """add_run() still adds the function despite deprecation."""
        bench_runner = bch.BenchRunner("test_deprecation")
        bench_fn = lambda run_cfg: None  # noqa: E731
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            bench_runner.add_run(bench_fn)
        self.assertIn(bench_fn, bench_runner.bench_fns)

    def test_add_does_not_emit_deprecation_warning(self):
        """add() does NOT emit a DeprecationWarning."""
        bench_runner = bch.BenchRunner("test_no_deprecation")
        bench_fn = lambda run_cfg: None  # noqa: E731
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bench_runner.add(bench_fn)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            self.assertEqual(len(deprecation_warnings), 0)

    def test_add_returns_self_for_chaining(self):
        """add() returns self for method chaining."""
        bench_runner = bch.BenchRunner("test_chaining")
        bench_fn = lambda run_cfg: None  # noqa: E731
        result = bench_runner.add(bench_fn)
        self.assertIs(result, bench_runner)


if __name__ == "__main__":
    unittest.main()
