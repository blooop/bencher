import unittest
import bencher as bch

from bencher.example.meta.example_meta import example_meta

import os


class TestBenchExamples(unittest.TestCase):
    """The purpose of this test class is to run the example problems to make sure they don't crash.  The bencher logic is tested in the other test files test_bencher.py and test_vars.py"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generate_all = False

    def create_run_cfg(self) -> bch.BenchRunCfg:
        cfg = bch.BenchRunCfg()
        if not self.generate_all:
            cfg.repeats = 2  # low number of repeats to reduce test time, but also test averaging and variance code
            cfg.level = 2  # reduce size of param sweep so tests are faster
        cfg.clear_cache = True
        return cfg

    def examples_asserts(self, example_result, save=False) -> None:
        self.assertIsNotNone(example_result)
        if save or self.generate_all:
            path = example_result.report.save_index("cachedir")
            self.assertTrue(os.path.exists(path))

    def test_example_meta(self) -> None:
        self.examples_asserts(example_meta(self.create_run_cfg()))
