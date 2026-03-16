"""Tests for bencher/results/holoview_results/holoview_result.py"""

import unittest
import holoviews as hv
import panel as pn

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.bench_result_base import ReduceType
from bencher.variables.results import ResultVar, ResultImage, ResultVideo


class TestHoloviewResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bench1 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=1))
        cls.res_1d = bench1.plot_sweep(
            "test_hv",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench2 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=2))
        cls.res_1d_r2 = bench2.plot_sweep(
            "test_hv_r2",
            input_vars=[BenchableObject.param.float1],
            result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
            run_cfg=bch.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

        bench3 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=1))
        cls.res_2d = bench3.plot_sweep(
            "test_hv_2d",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=1),
            plot_callbacks=False,
        )

        bench4 = BenchableObject().to_bench(bch.BenchRunCfg(repeats=2))
        cls.res_2d_r2 = bench4.plot_sweep(
            "test_hv_2d_r2",
            input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
            result_vars=[BenchableObject.param.distance],
            run_cfg=bch.BenchRunCfg(repeats=2),
            plot_callbacks=False,
        )

    def test_set_default_opts(self):
        result = HoloviewResult.set_default_opts()
        self.assertIn("width", result)
        self.assertIn("height", result)
        self.assertIn("tools", result)
        self.assertEqual(result["width"], 600)
        self.assertEqual(result["height"], 600)

    def test_set_default_opts_custom(self):
        result = HoloviewResult.set_default_opts(width=800, height=400)
        self.assertEqual(result["width"], 800)
        self.assertEqual(result["height"], 400)

    def test_to_hv_type_curve(self):
        chart = self.res_1d.to_hv_type(hv.Curve)
        self.assertIsInstance(chart, hv.Element)

    def test_to_hv_type_bars(self):
        chart = self.res_1d.to_hv_type(hv.Bars)
        self.assertIsInstance(chart, hv.Element)

    def test_to_hv_type_2d_points(self):
        chart = self.res_2d.to_hv_type(hv.Points)
        self.assertIsInstance(chart, hv.Element)

    def test_overlay_plots(self):
        def plot_cb(rv):
            return self.res_1d.to_hv_dataset().to(hv.Curve)

        result = self.res_1d.overlay_plots(plot_cb)
        self.assertIsInstance(result, hv.Overlay)

    def test_overlay_plots_returns_none(self):
        result = self.res_1d.overlay_plots(lambda rv: None)
        self.assertIsNone(result)

    def test_overlay_plots_markdown(self):
        result = self.res_1d.overlay_plots(lambda rv: pn.pane.Markdown(f"# {rv.name}"))
        self.assertIsInstance(result, pn.Row)

    def test_layout_plots(self):
        def plot_cb(rv):
            return self.res_1d.to_hv_dataset().to(hv.Curve)

        result = self.res_1d.layout_plots(plot_cb)
        self.assertIsInstance(result, hv.Layout)

    def test_layout_plots_none_results(self):
        result = self.res_1d.layout_plots(lambda rv: None)
        self.assertIsNone(result)

    def test_time_widget(self):
        widget = self.res_1d.time_widget("Test Title")
        self.assertIsInstance(widget, dict)
        self.assertEqual(widget["title"], "Test Title")

    def test_hv_container_ds(self):
        ds = self.res_1d.to_dataset()
        rv = self.res_1d.bench_cfg.result_vars[0]
        result = self.res_1d.hv_container_ds(ds, rv, container=hv.Bars)
        self.assertIsInstance(result, hv.Element)

    def test_to_hv_container(self):
        result = self.res_1d.to_hv_container(hv.Bars)
        self.assertIsInstance(result, pn.Row)

    def test_result_var_to_container_column(self):
        # Static-like method — no sweep data needed
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

    def test_to_error_bar(self):
        result = self.res_1d_r2.to_error_bar()
        self.assertIsInstance(result, hv.Element)

    def test_to_points(self):
        result = self.res_2d.to_points()
        self.assertIsInstance(result, hv.Element)

    def test_to_points_reduce(self):
        result = self.res_2d_r2.to_points(reduce=ReduceType.REDUCE)
        self.assertIsInstance(result, hv.Element)
