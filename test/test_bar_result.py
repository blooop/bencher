"""Tests for bencher/results/holoview_results/bar_result.py"""

import math
import unittest

import holoviews as hv
import panel as pn

import bencher as bn
from bencher.results.holoview_results.bar_result import BarResult
from test.helpers import run_named_sweep as _run_sweep


class Cat1DBench(bn.ParametrizedSweep):
    """Minimal 1-categorical sweep accepted by the bar filter (0 floats, 1 cat)."""

    method = bn.StringSweep(["alpha", "beta", "gamma"])
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = len(self.method) * 1.5


class Cat1DNanBench(bn.ParametrizedSweep):
    """Sweep where the worker returns NaN for one point (missing-value default)."""

    method = bn.StringSweep(["alpha", "beta", "gamma"])
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = float("nan") if self.method == "beta" else len(self.method) * 1.5


class TwoCatBench(bn.ParametrizedSweep):
    """Two categorical inputs so the bar chart groups by the second cat."""

    method = bn.StringSweep(["alpha", "beta"])
    backend = bn.StringSweep(["cpu", "gpu"])
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = len(self.method) + len(self.backend) * 0.5


class BoolBench(bn.ParametrizedSweep):
    """ResultBool sweep for the repeats>=2 REDUCE scenario of to_bar."""

    method = bn.StringSweep(["alpha", "beta"])
    passed = bn.ResultBool()

    def benchmark(self):
        self.passed = self.method == "alpha"


class Float1DBench(bn.ParametrizedSweep):
    """Float-input sweep that the bar filter (float_range 0..0) must reject."""

    x = bn.FloatSweep(bounds=(0, 1))
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = self.x * 2


class TestBarResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res_cat = _run_sweep(Cat1DBench, "bar_cat", ["method"], ["score"])
        cls.res_nan = _run_sweep(Cat1DNanBench, "bar_nan", ["method"], ["score"])
        cls.res_2cat = _run_sweep(TwoCatBench, "bar_2cat", ["method", "backend"], ["score"])
        cls.res_bool = _run_sweep(BoolBench, "bar_bool", ["method"], ["passed"], repeats=2)
        cls.res_float = _run_sweep(Float1DBench, "bar_float", ["x"], ["score"])

    def test_to_bar_returns_row_with_bars(self):
        result = self.res_cat.to_bar()
        self.assertIsInstance(result, pn.Row)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], pn.pane.HoloViews)
        self.assertIsInstance(result[0].object, hv.Bars)

    def test_to_plot_delegates_to_bar(self):
        result = BarResult.to_plot(self.res_cat)
        self.assertIsInstance(result, pn.Row)
        self.assertIsInstance(result[0].object, hv.Bars)

    def test_to_bar_ds_dims_and_labels(self):
        """Input var on kdims, result var on vdims, ylabel includes units."""
        ds = self.res_cat.to_dataset()
        rv = self.res_cat.bench_cfg.result_vars[0]
        result = self.res_cat.to_bar_ds(ds, rv)
        self.assertIsInstance(result, pn.pane.HoloViews)
        element = result.object
        self.assertIsInstance(element, hv.Bars)
        self.assertEqual(element.kdims[0].name, "method")
        self.assertEqual(element.vdims[0].name, "score")
        opts = element.opts.get().kwargs
        self.assertEqual(opts["title"], "score vs method")
        self.assertEqual(opts["ylabel"], "score [m]")

    def test_to_bar_bool_with_repeats(self):
        """ResultBool with repeats>=2 matches the REDUCE scenario and still plots."""
        result = self.res_bool.to_bar()
        self.assertIsInstance(result, pn.Row)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0].object, hv.Bars)

    def test_to_bar_groups_by_extra_cats(self):
        """With two categorical inputs the second cat becomes the by grouping."""
        ds = self.res_2cat.to_dataset()
        rv = self.res_2cat.bench_cfg.result_vars[0]
        result = self.res_2cat.to_bar_ds(ds, rv)
        self.assertIsInstance(result, pn.pane.HoloViews)
        element = result.object
        kdim_names = [d.name for d in element.kdims]
        self.assertIn("method", kdim_names)
        self.assertIn("backend", kdim_names)

    def test_to_bar_nan_does_not_crash(self):
        ds = self.res_nan.to_dataset()
        self.assertTrue(any(math.isnan(v) for v in ds["score"].values.ravel()))
        result = self.res_nan.to_bar()
        self.assertIsInstance(result, pn.Row)
        self.assertIsInstance(result[0].object, hv.Bars)

    def test_to_bar_rejects_float_sweep(self):
        """A float input sweep fails the float_range=(0,0) filter when override=False.

        The filter returns None (or a Markdown debug panel), never a bar pane.
        """
        result = self.res_float.to_bar(override=False)
        self.assertNotIsInstance(result, (pn.Row, pn.pane.HoloViews))
        if result is not None:
            self.assertIsInstance(result, pn.pane.Markdown)
