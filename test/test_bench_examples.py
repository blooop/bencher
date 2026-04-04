import inspect
import unittest

import bencher as bn

from bencher.example.meta.example_meta import example_meta

import os


class TestBenchExamples(unittest.TestCase):
    """Run example problems to make sure they don't crash."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generate_all = False

    def create_run_cfg(self) -> bn.BenchRunCfg:
        cfg = bn.BenchRunCfg()
        if not self.generate_all:
            cfg.repeats = 2
            cfg.level = 2
        cfg.clear_cache = True
        return cfg

    def examples_asserts(self, example_result, save=False) -> None:
        self.assertIsNotNone(example_result)
        if save or self.generate_all:
            path = example_result.report.save_index("cachedir")
            self.assertTrue(os.path.exists(path))

    def test_example_meta(self) -> None:
        self.examples_asserts(example_meta(self.create_run_cfg(), sample_repeats_values=[1, 3]))

    def test_example_meta_default_sample_repeats(self) -> None:
        """Verify the default sample_repeats_values is [1, 10] without running the full sweep."""
        sig = inspect.signature(example_meta)
        self.assertIsNone(sig.parameters["sample_repeats_values"].default)
