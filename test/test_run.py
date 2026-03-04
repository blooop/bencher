"""Tests for the bch.run() convenience function."""

import unittest
import bencher as bch
from bencher.example.example_simple_float import SimpleFloat, example_simple_float


class TestRun(unittest.TestCase):
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

    def test_run_with_level_and_repeats(self):
        """bch.run() passes level and repeats through correctly."""
        results = bch.run(example_simple_float, level=2, repeats=2, show=False)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

    def test_run_with_save(self):
        """bch.run() with save=True doesn't crash."""
        results = bch.run(example_simple_float, show=False, save=True)
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
