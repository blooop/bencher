"""Tests for bencher/results/holoview_results/holoview_result.py"""

import unittest
import holoviews as hv
import panel as pn

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.bench_result_base import ReduceType
from bencher.variables.results import ResultVar, ResultImage, ResultVideo


def _run_1d_sweep(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_hv",
        input_vars=[BenchableObject.param.float1],
        result_vars=[BenchableObject.param.distance, BenchableObject.param.sample_noise],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


def _run_2d_sweep(repeats=1):
    bench = BenchableObject().to_bench(bch.BenchRunCfg(repeats=repeats))
    return bench.plot_sweep(
        "test_hv_2d",
        input_vars=[BenchableObject.param.float1, BenchableObject.param.float2],
        result_vars=[BenchableObject.param.distance],
        run_cfg=bch.BenchRunCfg(repeats=repeats),
        plot_callbacks=False,
    )


class TestHoloviewResult(unittest.TestCase):
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
        res = _run_1d_sweep()
        chart = res.to_hv_type(hv.Curve)
        self.assertIsNotNone(chart)

    def test_to_hv_type_bars(self):
        res = _run_1d_sweep()
        chart = res.to_hv_type(hv.Bars)
        self.assertIsNotNone(chart)

    def test_to_hv_type_2d_points(self):
        res = _run_2d_sweep()
        chart = res.to_hv_type(hv.Points)
        self.assertIsNotNone(chart)

    def test_overlay_plots(self):
        res = _run_1d_sweep()

        def plot_cb(rv):
            ds = res.to_hv_dataset()
            return ds.to(hv.Curve)

        result = res.overlay_plots(plot_cb)
        self.assertIsNotNone(result)

    def test_overlay_plots_returns_none(self):
        res = _run_1d_sweep()

        def plot_cb(rv):
            return None

        result = res.overlay_plots(plot_cb)
        self.assertIsNone(result)

    def test_overlay_plots_markdown(self):
        res = _run_1d_sweep()

        def plot_cb(rv):
            return pn.pane.Markdown(f"# {rv.name}")

        result = res.overlay_plots(plot_cb)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, pn.Row)

    def test_layout_plots(self):
        res = _run_1d_sweep()

        def plot_cb(rv):
            ds = res.to_hv_dataset()
            return ds.to(hv.Curve)

        result = res.layout_plots(plot_cb)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, hv.Layout)

    def test_layout_plots_none_results(self):
        res = _run_1d_sweep()

        def plot_cb(rv):
            return None

        result = res.layout_plots(plot_cb)
        self.assertIsNone(result)

    def test_time_widget(self):
        res = _run_1d_sweep()
        widget = res.time_widget("Test Title")
        self.assertIsInstance(widget, dict)
        self.assertEqual(widget["title"], "Test Title")

    def test_hv_container_ds(self):
        res = _run_1d_sweep()
        ds = res.to_dataset()
        rv = res.bench_cfg.result_vars[0]
        result = res.hv_container_ds(ds, rv, container=hv.Bars)
        self.assertIsNotNone(result)

    def test_to_hv_container(self):
        res = _run_1d_sweep()
        result = res.to_hv_container(hv.Bars)
        self.assertIsNotNone(result)

    def test_result_var_to_container_column(self):
        res = _run_1d_sweep()
        rv = ResultVar()
        container = res.result_var_to_container(rv)
        self.assertEqual(container, pn.Column)

    def test_result_var_to_container_image(self):
        res = _run_1d_sweep()
        rv = ResultImage()
        container = res.result_var_to_container(rv)
        self.assertEqual(container, pn.pane.PNG)

    def test_result_var_to_container_video(self):
        res = _run_1d_sweep()
        rv = ResultVideo()
        container = res.result_var_to_container(rv)
        self.assertEqual(container, pn.pane.Video)

    def test_setup_results_and_containers_default(self):
        res = _run_1d_sweep()
        rv = ResultVar()
        vars_out, containers = res.setup_results_and_containers(rv)
        self.assertEqual(len(vars_out), 1)
        self.assertEqual(len(containers), 1)
        self.assertIsInstance(containers[0], pn.Column)

    def test_setup_results_and_containers_explicit(self):
        res = _run_1d_sweep()
        rv = ResultVar()
        vars_out, containers = res.setup_results_and_containers(rv, container=pn.Column)
        self.assertEqual(len(vars_out), 1)
        self.assertEqual(len(containers), 1)

    def test_to_error_bar(self):
        res = _run_1d_sweep(repeats=2)
        result = res.to_error_bar()
        self.assertIsNotNone(result)

    def test_to_points(self):
        res = _run_2d_sweep()
        result = res.to_points()
        self.assertIsNotNone(result)

    def test_to_points_reduce(self):
        res = _run_2d_sweep(repeats=2)
        result = res.to_points(reduce=ReduceType.REDUCE)
        self.assertIsNotNone(result)
