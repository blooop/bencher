"""Tests for bencher/results/holoview_results/line_result.py"""

import unittest

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


class TestLineResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_1d = bench.plot_sweep(
            "test_line",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_cat = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_1d_cat = bench_cat.plot_sweep(
            "test_line_cat",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.wave],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

    def test_to_line_ds(self):
        ds = self.res_1d.to_dataset()
        rv = self.res_1d.bench_cfg.result_vars[0]
        result = self.res_1d.to_line_ds(ds, rv)
        self.assertIsNotNone(result)

    def test_to_line(self):
        result = self.res_1d.to_line()
        self.assertIsNotNone(result)

    def test_to_plot(self):
        """Test to_plot delegates to to_line."""
        from bencher.results.holoview_results.line_result import LineResult

        result = LineResult.to_plot(self.res_1d)
        self.assertIsNotNone(result)

    def test_to_line_no_tap(self):
        result = self.res_1d.to_line(use_tap=False)
        self.assertIsNotNone(result)

    def test_to_line_with_cat(self):
        result = self.res_1d_cat.to_line()
        self.assertIsNotNone(result)

    def test_to_line_ds_with_cat(self):
        ds = self.res_1d_cat.to_dataset()
        rv = self.res_1d_cat.bench_cfg.result_vars[0]
        result = self.res_1d_cat.to_line_ds(ds, rv)
        self.assertIsNotNone(result)
