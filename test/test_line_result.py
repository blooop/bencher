"""Tests for bencher/results/holoview_results/line_result.py"""

import unittest

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def _run_1d_sweep(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_line",
        input_vars=[BenchableObject.param.float1],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


def _run_1d_sweep_with_cat(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_line_cat",
        input_vars=[BenchableObject.param.float1, BenchableObject.param.wave],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


class TestLineResult(unittest.TestCase):
    def test_to_line_ds(self):
        res = _run_1d_sweep()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_line_ds(ds, rv)
        self.assertIsNotNone(result)

    def test_to_line(self):
        res = _run_1d_sweep()
        result = res.to_line()
        self.assertIsNotNone(result)

    def test_to_plot(self):
        """Test to_plot delegates to to_line."""
        from bencher.results.holoview_results.line_result import LineResult

        res = _run_1d_sweep()
        result = LineResult.to_plot(res)
        self.assertIsNotNone(result)

    def test_to_line_no_tap(self):
        res = _run_1d_sweep()
        result = res.to_line(use_tap=False)
        self.assertIsNotNone(result)

    def test_to_line_with_cat(self):
        res = _run_1d_sweep_with_cat()
        result = res.to_line()
        self.assertIsNotNone(result)

    def test_to_line_ds_with_cat(self):
        res = _run_1d_sweep_with_cat()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_line_ds(ds, rv)
        self.assertIsNotNone(result)
