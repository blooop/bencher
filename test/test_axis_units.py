"""Tests that curve, line and scatter plots show result-var units on their axes.

Follow-up to https://github.com/blooop/bencher/pull/960: histogram gained units
there, and band/bar/heatmap/surface/distribution already showed them. These
tests cover the remaining gaps (curve/line/scatter) plus the shared
``label_with_units`` helper.
"""

import unittest
import warnings

import holoviews as hv

import bencher as bn
from bencher.utils import label_with_units


def _unwrap_hv(obj):
    """Unwrap a panel Row/HoloViews pane returned by filter() to the hv object inside."""
    while True:
        if hasattr(obj, "object"):
            obj = obj.object
        elif hasattr(obj, "objects"):
            assert len(obj.objects) > 0
            obj = obj.objects[0]
        else:
            return obj


def _find_element(obj, element_type):
    """Depth-first search for the first holoviews element of the given type."""
    obj = _unwrap_hv(obj)
    if isinstance(obj, element_type):
        return obj
    if hasattr(obj, "traverse"):
        found = obj.traverse(lambda x: x, [element_type])
        if found:
            return found[0]
    return None


class FloatBench(bn.ParametrizedSweep):
    """1-float sweep with units on both the input and the result."""

    distance = bn.FloatSweep(default=0, bounds=[0, 10], units="m", samples=4)
    throughput = bn.ResultFloat(units="ops/s")

    def benchmark(self):
        self.throughput = self.distance * 2.0 + 1.0


with warnings.catch_warnings():
    # ResultVar is deprecated, but to_scatter's result_types filter only accepts it.
    warnings.simplefilter("ignore", DeprecationWarning)

    class CatBench(bn.ParametrizedSweep):
        """1-categorical sweep accepted by the scatter filter."""

        method = bn.StringSweep(["alpha", "beta"])
        score = bn.ResultVar(units="m")

        def benchmark(self):
            self.score = float(len(self.method))


def _run_sweep(bench_class, name, input_vars, result_vars, repeats):
    run_cfg = bn.BenchRunCfg(
        repeats=repeats, cache_results=False, cache_samples=False, auto_plot=False
    )
    bench = bn.Bench(name, bench_class(), run_cfg=run_cfg)
    return bench.plot_sweep(
        name, input_vars=input_vars, result_vars=result_vars, plot_callbacks=False
    )


class _LabelBench(bn.ParametrizedSweep):
    """Params must be class-bound for param to assign their names."""

    with_units = bn.ResultFloat(units="ms")
    no_units = bn.ResultFloat(units="")
    unitless = bn.ResultFloat(units="ul")


class TestLabelWithUnits(unittest.TestCase):
    def test_name_and_units(self):
        self.assertEqual(label_with_units(_LabelBench.param.with_units), "with_units [ms]")

    def test_no_units(self):
        self.assertEqual(label_with_units(_LabelBench.param.no_units), "no_units")

    def test_unitless_convention(self):
        """'ul' is the sweep-variable convention for unitless and must not be shown."""
        self.assertEqual(label_with_units(_LabelBench.param.unitless), "unitless")

    def test_no_units_attribute(self):
        """Objects without a ``units`` attribute fall back to just the name."""

        class _NoUnits:
            name = "bare"

        self.assertEqual(label_with_units(_NoUnits()), "bare")

    def test_units_none(self):
        """``units=None`` is treated the same as no units."""

        class _NoneUnits:
            name = "nothing"
            units = None

        self.assertEqual(label_with_units(_NoneUnits()), "nothing")


class TestCurveAxisUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _run_sweep(FloatBench, "units_curve", ["distance"], ["throughput"], repeats=2)

    def test_curve_axis_labels_show_units(self):
        curve = _find_element(self.res.to_curve(), hv.Curve)
        self.assertIsNotNone(curve)
        opts = curve.opts.get().kwargs
        self.assertEqual(opts["xlabel"], "distance [m]")
        self.assertEqual(opts["ylabel"], "throughput [ops/s]")


class TestLineAxisUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _run_sweep(FloatBench, "units_line", ["distance"], ["throughput"], repeats=1)

    def _assert_line_axis_labels(self, curve):
        self.assertIsNotNone(curve)
        opts = curve.opts.get().kwargs
        self.assertEqual(opts["xlabel"], "distance [m]")
        self.assertEqual(opts["ylabel"], "throughput [ops/s]")

    def test_line_axis_labels_show_units(self):
        # float-x path: LineResult.to_line_ds
        self._assert_line_axis_labels(_find_element(self.res.to_line(use_tap=False), hv.Curve))

    def test_line_tap_axis_labels_show_units(self):
        # tap path: LineResult._to_line_tap_ds
        self._assert_line_axis_labels(_find_element(self.res.to_line(use_tap=True), hv.Curve))


class TestScatterAxisUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = _run_sweep(CatBench, "units_scatter", ["method"], ["score"], repeats=1)

    def test_scatter_axis_labels_show_units(self):
        scatter = _find_element(self.res.to_scatter(), hv.Scatter)
        self.assertIsNotNone(scatter)
        opts = scatter.opts.get().kwargs
        self.assertEqual(opts["ylabel"], "score [m]")
        # StringSweep defaults to unitless ("ul"), so the x label stays the bare name
        self.assertEqual(opts["xlabel"], "method")


if __name__ == "__main__":
    unittest.main()
