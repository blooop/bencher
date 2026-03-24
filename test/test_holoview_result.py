"""Tests for bencher/results/holoview_results/holoview_result.py"""

import unittest
import plotly.graph_objects as go

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.bench_result_base import ReduceType, DatasetWrapper


class TestHoloviewResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench1 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_1d = bench1.plot_sweep(
            "test_hv",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench2 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=2))
        cls.res_1d_r2 = bench2.plot_sweep(
            "test_hv_r2",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        bench3 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=1))
        cls.res_2d = bench3.plot_sweep(
            "test_hv_2d",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench4 = BenchableObject().to_bench(bn.BenchRunCfg(repeats=2))
        cls.res_2d_r2 = bench4.plot_sweep(
            "test_hv_2d_r2",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bn.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

    def test_to_hv_dataset_returns_wrapper(self):
        result = self.res_1d.to_hv_dataset()
        self.assertIsInstance(result, DatasetWrapper)
        self.assertIsNotNone(result.data)

    def test_build_curve_overlay_returns_plotly_figure(self):
        ds = self.res_1d_r2.to_dataset(ReduceType.REDUCE)
        rv = self.res_1d_r2.bench_cfg.result_vars[0]
        fig = self.res_1d_r2._build_curve_overlay(ds, rv)  # pylint: disable=protected-access
        self.assertIsInstance(fig, go.Figure)
        self.assertGreater(len(fig.data), 0)

    def test_subsample_indices_no_subsample(self):
        indices = HoloviewResult.subsample_indices(10, None)
        self.assertEqual(list(indices), list(range(10)))

    def test_subsample_indices_with_limit(self):
        indices = HoloviewResult.subsample_indices(100, 10)
        self.assertEqual(len(indices), 10)
        self.assertEqual(indices[0], 0)
        self.assertEqual(indices[-1], 99)
