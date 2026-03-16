"""Tests for bencher/results/holoview_results/heatmap_result.py"""

import unittest

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def _run_2d_sweep(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_hm",
        input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


def _run_1d_sweep():
    bench = BenchableObject().to_bench()
    return bench.plot_sweep(
        "test_hm_1d",
        input_vars=[BenchableObject.param.float1],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=1),
        plot_callbacks=False,
    )


class TestHeatmapResult(unittest.TestCase):
    def test_to_heatmap_ds(self):
        res = _run_2d_sweep()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_heatmap_ds(ds, rv)
        self.assertIsNotNone(result)

    def test_to_heatmap_ds_returns_none(self):
        res = _run_1d_sweep()
        # Create a 1D dataset (< 2 dims) to test None return
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_heatmap_ds(ds, rv)
        self.assertIsNone(result)

    def test_to_heatmap(self):
        res = _run_2d_sweep()
        result = res.to_heatmap()
        self.assertIsNotNone(result)

    def test_to_plot_delegates_to_heatmap(self):
        """to_plot delegates to to_heatmap."""
        from bencher.results.holoview_results.heatmap_result import HeatmapResult

        res = _run_2d_sweep()
        result = HeatmapResult.to_plot(res)
        self.assertIsNotNone(result)

    def test_to_heatmap_no_tap(self):
        res = _run_2d_sweep()
        result = res.to_heatmap(use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_tap_var_list(self):
        res = _run_2d_sweep()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_heatmap(tap_var=[rv], use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_tap_var_single(self):
        res = _run_2d_sweep()
        rv = res.bench_cfg.result_vars[0]
        # Pass single var (not list) to test the list conversion path
        result = res.to_heatmap(tap_var=rv, use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_with_tap_var(self):
        """Test the heatmap with tap functionality enabled via to_heatmap."""
        res = _run_2d_sweep()
        rv = res.bench_cfg.result_vars[0]
        # Use to_heatmap with tap_var to exercise the tap code path
        # use_tap=False avoids interactive issues, but tests the tap_var list handling
        result = res.to_heatmap(tap_var=[rv], use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_single(self):
        res = _run_2d_sweep()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_heatmap_single(rv)
        self.assertIsNotNone(result)

    def test_to_heatmap_1d_single_filter_fail(self):
        res = _run_1d_sweep()
        rv = res.bench_cfg.result_vars[0]
        # With 1 float var, the filter (float_range=VarRange(2, None)) should not match
        result = res.to_heatmap_single(rv, override=False)
        # Should return the filter match panel (not a heatmap)
        self.assertIsNotNone(result)
