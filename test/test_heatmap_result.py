"""Tests for bencher/results/holoview_results/heatmap_result.py"""

import unittest

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


class TestHeatmapResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench_2d = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_2d = bench_2d.plot_sweep(
            "test_hm",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_1d = BenchableObject().to_bench()
        cls.res_1d = bench_1d.plot_sweep(
            "test_hm_1d",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

    def test_to_heatmap_ds(self):
        ds = self.res_2d.to_dataset()
        rv = self.res_2d.bench_cfg.result_vars[0]
        result = self.res_2d.to_heatmap_ds(ds, rv)
        self.assertIsNotNone(result)

    def test_to_heatmap_ds_returns_none(self):
        ds = self.res_1d.to_dataset()
        rv = self.res_1d.bench_cfg.result_vars[0]
        result = self.res_1d.to_heatmap_ds(ds, rv)
        self.assertIsNone(result)

    def test_to_heatmap(self):
        result = self.res_2d.to_heatmap()
        self.assertIsNotNone(result)

    def test_to_plot_delegates_to_heatmap(self):
        """to_plot delegates to to_heatmap."""
        from bencher.results.holoview_results.heatmap_result import HeatmapResult

        result = HeatmapResult.to_plot(self.res_2d)
        self.assertIsNotNone(result)

    def test_to_heatmap_no_tap(self):
        result = self.res_2d.to_heatmap(use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_tap_var_single(self):
        rv = self.res_2d.bench_cfg.result_vars[0]
        # Pass single var (not list) to test the list conversion path (line 101-102)
        result = self.res_2d.to_heatmap(tap_var=rv, use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_tap_var_list(self):
        rv = self.res_2d.bench_cfg.result_vars[0]
        # Pass list tap_var with use_tap=False to exercise list-handling (lines 99-112)
        result = self.res_2d.to_heatmap(tap_var=[rv], use_tap=False)
        self.assertIsNotNone(result)

    def test_to_heatmap_suppressed_for_cat_only_inputs(self):
        """Heatmap auto-plot must not fire when there are <2 float vars (cat-only inputs).

        For 2 cats / 0 floats the new filter rejects, so the auto path returns
        a Markdown debug panel (or None) rather than a HoloViews heatmap pane.
        """
        import holoviews as hv

        bench_cat = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        res_cat = bench_cat.plot_sweep(
            "test_hm_cat_only",
            input_vars=[BenchableObject.param.wave, BenchableObject.param.variant],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )
        result = res_cat.to_heatmap(override=False)
        self.assertNotIsInstance(result, (hv.HeatMap, hv.HoloMap))
