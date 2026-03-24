"""Tests for bencher/results/holoview_results/surface_result.py"""

import unittest
import plotly.graph_objects as go

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


class TestSurfaceResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench_2d = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_2d = bench_2d.plot_sweep(
            "test_surface",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench_2d_r2 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=2))
        cls.res_2d_r2 = bench_2d_r2.plot_sweep(
            "test_surface_r2",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        bench_1d = BenchableObject().to_bench()
        cls.res_1d = bench_1d.plot_sweep(
            "test_surface_1d",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

    def test_to_surface(self):
        result = self.res_2d.to_surface()
        self.assertIsNotNone(result)

    def test_to_plot(self):
        """Test to_plot delegates to to_surface."""
        from bencher.results.holoview_results.surface_result import SurfaceResult

        result = SurfaceResult.to_plot(self.res_2d)
        self.assertIsNotNone(result)

    def test_to_surface_ds(self):
        ds = self.res_2d_r2.to_dataset()
        rv = self.res_2d_r2.bench_cfg.result_vars[0]
        result = self.res_2d_r2.to_surface_ds(ds, rv)
        self.assertIsInstance(result, go.Figure)

    def test_to_surface_ds_with_std(self):
        ds = self.res_2d_r2.to_dataset()
        rv = self.res_2d_r2.bench_cfg.result_vars[0]
        # With repeats > 1, should show std-dev bounds
        result = self.res_2d_r2.to_surface_ds(ds, rv)
        self.assertIsInstance(result, go.Figure)

    def test_to_surface_1d_filter_fail(self):
        """1D data doesn't match the 2-float requirement for surface plots."""
        from bencher.results.holoview_results.surface_result import SurfaceResult

        result = SurfaceResult.to_surface(self.res_1d, override=False)
        # Filter rejects — returns None or a Markdown debug panel, not a Plotly surface
        self.assertNotIsInstance(result, go.Figure)
