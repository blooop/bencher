"""Tests for bencher/results/holoview_results/surface_result.py"""

import unittest
import panel as pn

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def _run_2d_sweep(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_surface",
        input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


def _run_1d_sweep():
    bench = BenchableObject().to_bench()
    return bench.plot_sweep(
        "test_surface_1d",
        input_vars=[BenchableObject.param.float1],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=1),
        plot_callbacks=False,
    )


class TestSurfaceResult(unittest.TestCase):
    def test_to_surface(self):
        res = _run_2d_sweep()
        result = res.to_surface()
        self.assertIsNotNone(result)

    def test_to_plot(self):
        """Test to_plot delegates to to_surface."""
        from bencher.results.holoview_results.surface_result import SurfaceResult

        res = _run_2d_sweep()
        result = SurfaceResult.to_plot(res)
        self.assertIsNotNone(result)

    def test_to_surface_ds(self):
        res = _run_2d_sweep(repeats=2)
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.to_surface_ds(ds, rv)
        self.assertIsNotNone(result)

    def test_to_surface_ds_with_std(self):
        res = _run_2d_sweep(repeats=2)
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        # With repeats > 1, should show std-dev bounds
        result = res.to_surface_ds(ds, rv)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, pn.pane.Plotly)

    def test_to_surface_1d_filter_fail(self):
        """1D data doesn't match the 2-float requirement for surface plots."""
        from bencher.results.holoview_results.surface_result import SurfaceResult

        res = _run_1d_sweep()
        result = SurfaceResult.to_surface(res, override=False)
        # Filter rejects — returns None or a Markdown debug panel, not a Plotly surface
        self.assertNotIsInstance(result, pn.pane.Plotly)
