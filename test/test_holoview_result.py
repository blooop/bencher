"""Tests for bencher/results/holoview_results/holoview_result.py"""

import unittest
import panel as pn
import plotly.graph_objects as go

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.bench_result_base import ReduceType, DatasetWrapper
from bencher.variables.results import ResultVar, ResultImage, ResultVideo


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

    def test_set_default_opts(self):
        result = HoloviewResult.set_default_opts()
        self.assertIn("width", result)
        self.assertIn("height", result)
        self.assertEqual(result["width"], 600)
        self.assertEqual(result["height"], 500)

    def test_set_default_opts_custom(self):
        result = HoloviewResult.set_default_opts(width=800, height=400)
        self.assertEqual(result["width"], 800)
        self.assertEqual(result["height"], 400)

    def test_to_hv_dataset_returns_wrapper(self):
        result = self.res_1d.to_hv_dataset()
        self.assertIsInstance(result, DatasetWrapper)
        self.assertIsNotNone(result.data)

    def test_overlay_plots_returns_none_for_none(self):
        result = self.res_1d.overlay_plots(lambda rv: None)
        self.assertIsNone(result)

    def test_time_widget(self):
        widget = self.res_1d.time_widget("Test Title")
        self.assertIsInstance(widget, dict)
        self.assertEqual(widget["title"], "Test Title")

    def test_result_var_to_container_column(self):
        container = HoloviewResult.result_var_to_container(self.res_1d, ResultVar())
        self.assertEqual(container, pn.Column)

    def test_result_var_to_container_image(self):
        container = HoloviewResult.result_var_to_container(self.res_1d, ResultImage())
        self.assertEqual(container, pn.pane.PNG)

    def test_result_var_to_container_video(self):
        container = HoloviewResult.result_var_to_container(self.res_1d, ResultVideo())
        self.assertEqual(container, pn.pane.Video)

    def test_setup_results_and_containers_default(self):
        rv = ResultVar()
        vars_out, containers = self.res_1d.setup_results_and_containers(rv)
        self.assertEqual(len(vars_out), 1)
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0], pn.Column)

    def test_setup_results_and_containers_explicit(self):
        rv = ResultVar()
        vars_out, containers = self.res_1d.setup_results_and_containers(rv, container=pn.Column)
        self.assertEqual(len(vars_out), 1)
        self.assertEqual(len(containers), 1)

    def test_build_curve_overlay_returns_plotly_figure(self):
        ds = self.res_1d_r2.to_dataset(ReduceType.REDUCE)
        rv = self.res_1d_r2.bench_cfg.result_vars[0]
        fig = self.res_1d_r2._build_curve_overlay(ds, rv)
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
