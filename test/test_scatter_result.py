"""Tests for bencher/results/holoview_results/scatter_result.py"""

import math
import unittest
import warnings

import holoviews as hv
import panel as pn

import bencher as bn
from bencher.results.holoview_results.scatter_result import ScatterResult
from test.helpers import run_named_sweep


class Cat1DBench(bn.ParametrizedSweep):
    """Minimal 1-categorical sweep accepted by the scatter filter (0 floats, 1 cat)."""

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
    """Two categorical inputs so the scatter groups by the second cat."""

    method = bn.StringSweep(["alpha", "beta"])
    backend = bn.StringSweep(["cpu", "gpu"])
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = len(self.method) + len(self.backend) * 0.5


class Float1DBench(bn.ParametrizedSweep):
    """Float-input sweep that the scatter filter (float_range 0..0) must reject."""

    x = bn.FloatSweep(bounds=(0, 1))
    score = bn.ResultFloat(units="m")

    def benchmark(self):
        self.score = self.x * 2


with warnings.catch_warnings():
    # ResultVar is deprecated, but to_scatter's result_types filter only accepts it,
    # so the full public path is exercised with a ResultVar result.
    warnings.simplefilter("ignore", DeprecationWarning)

    class LegacyScatterBench(bn.ParametrizedSweep):
        method = bn.StringSweep(["alpha", "beta"])
        score = bn.ResultVar(units="m")

        def benchmark(self):
            self.score = len(self.method) * 1.0


def _run_sweep(bench_class, name, input_vars, repeats=1):
    return run_named_sweep(bench_class, name, input_vars, ["score"], repeats)


class TestScatterResult(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res_cat = _run_sweep(Cat1DBench, "scatter_cat", ["method"])
        cls.res_nan = _run_sweep(Cat1DNanBench, "scatter_nan", ["method"])
        cls.res_2cat = _run_sweep(TwoCatBench, "scatter_2cat", ["method", "backend"])
        cls.res_float = _run_sweep(Float1DBench, "scatter_float", ["x"])
        cls.res_legacy = _run_sweep(LegacyScatterBench, "scatter_legacy", ["method"])

    def test_to_scatter_ds_returns_scatter_pane(self):
        ds = self.res_cat.to_dataset()
        rv = self.res_cat.bench_cfg.result_vars[0]
        result = self.res_cat._to_scatter_ds(ds, rv)  # pylint: disable=protected-access
        self.assertIsInstance(result, pn.pane.HoloViews)
        self.assertIsInstance(result.object, hv.Scatter)

    def test_to_scatter_ds_dims_and_title(self):
        """Input var on kdims, result var on vdims, title from to_plot_title."""
        ds = self.res_cat.to_dataset()
        rv = self.res_cat.bench_cfg.result_vars[0]
        result = self.res_cat._to_scatter_ds(ds, rv)  # pylint: disable=protected-access
        element = result.object
        self.assertEqual(element.kdims[0].name, "method")
        self.assertEqual(element.vdims[0].name, "score")
        self.assertEqual(element.opts.get().kwargs["title"], "score vs method")

    def test_to_scatter_full_path_with_result_var(self):
        """The public to_scatter path produces a Row of Scatter panes for ResultVar."""
        result = self.res_legacy.to_scatter()
        self.assertIsInstance(result, pn.Row)
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result[0], pn.pane.HoloViews)
        self.assertIsInstance(result[0].object, hv.Scatter)

    def test_to_plot_delegates_to_scatter(self):
        result = ScatterResult.to_plot(self.res_legacy)
        self.assertIsInstance(result, pn.Row)
        self.assertIsInstance(result[0].object, hv.Scatter)

    def test_to_scatter_result_float_returns_none(self):
        """Documents current behavior: result_types=(ResultVar,) excludes plain
        ResultFloat results, so the public to_scatter path yields no panes."""
        self.assertIsNone(self.res_cat.to_scatter())

    def test_to_scatter_ds_nan_does_not_crash(self):
        ds = self.res_nan.to_dataset()
        rv = self.res_nan.bench_cfg.result_vars[0]
        self.assertTrue(any(math.isnan(v) for v in ds["score"].values.ravel()))
        result = self.res_nan._to_scatter_ds(ds, rv)  # pylint: disable=protected-access
        self.assertIsInstance(result, pn.pane.HoloViews)
        self.assertIsInstance(result.object, hv.Scatter)

    def test_to_scatter_ds_groups_by_extra_cats(self):
        """With >1 categorical input, the scatter groups by the remaining cats."""
        ds = self.res_2cat.to_dataset()
        rv = self.res_2cat.bench_cfg.result_vars[0]
        result = self.res_2cat._to_scatter_ds(ds, rv)  # pylint: disable=protected-access
        self.assertIsInstance(result, pn.pane.HoloViews)
        self.assertIsInstance(result.object, hv.NdOverlay)
        self.assertEqual(result.object.kdims[0].name, "backend")

    def test_to_scatter_rejects_float_sweep(self):
        """A float input sweep fails the float_range=(0,0) filter when override=False.

        The filter returns None (or a Markdown debug panel), never a scatter pane.
        """
        result = self.res_float.to_scatter(override=False)
        self.assertNotIsInstance(result, (pn.Row, pn.pane.HoloViews))
        if result is not None:
            self.assertIsInstance(result, pn.pane.Markdown)
