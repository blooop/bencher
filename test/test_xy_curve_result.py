"""Tests for XYCurveResult / xy_curve (holoview_results/xy_curve_result.py)."""

import pickle
import unittest

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
import xarray as xr

import bencher as bn
from bencher.plugins import get_registry
from bencher.results.holoview_results.xy_curve_result import XYCurveResult, xy_curve
from test.helpers import run_cfg_with

DURATIONS = [1.0, 2.0]
SAMPLES_PER_TRACE = 6


def trace_frame(duration: float) -> pd.DataFrame:
    """A collected series: rows are the trace, columns are the axes."""
    t = np.linspace(0.0, duration, SAMPLES_PER_TRACE)
    return pd.DataFrame({"time": t, "signal": np.sin(t), "reference": np.cos(t)})


def xarray_trace_frame(duration: float) -> pd.DataFrame | pd.Series:
    """The same trace built the way xarray users build one.

    ``Dataset.to_pandas()`` leaves the dimension coordinate in the *index*, so the
    x axis is not a column until ``to_dataframe`` promotes it.
    """
    t = np.linspace(0.0, duration, SAMPLES_PER_TRACE)
    signal = xr.DataArray(np.sin(t), dims=["time"], coords={"time": t})
    # to_pandas() returns a Series for 1-D data and a DataFrame otherwise; ty sees the
    # union, so name it rather than narrowing on a shape it cannot see (plan 23 P12).
    return xr.Dataset({"signal": signal}).to_pandas()


class TraceSweep(bn.ParametrizedSweep):
    """Each sample collects a whole series, plus one scalar."""

    duration = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)

    trace = bn.ResultDataSet(doc="a collected series, one row per sample point")
    peak = bn.ResultFloat(units="v", doc="a scalar that is not a curve")

    def benchmark(self):
        self.trace = bn.ResultDataSet(trace_frame(self.duration))
        self.peak = float(np.sin(self.duration))


class DeclaredCurveSweep(bn.ParametrizedSweep):
    """The spec lives on the result var, so the trace renders with the other results."""

    duration = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    trace = bn.ResultDataSet(container=xy_curve(x="time", y="signal"))

    def benchmark(self):
        self.trace = bn.ResultDataSet(trace_frame(self.duration))


def run_sweep(worker: bn.ParametrizedSweep, name: str, result_vars: list[str]):
    bench = bn.Bench(name, worker, run_cfg=run_cfg_with(1))
    return bench.plot_sweep(
        name, input_vars=["duration"], result_vars=result_vars, plot_callbacks=False
    )


def all_curves(viewable: pn.viewable.Viewable) -> list[hv.Curve]:
    """Every hv.Curve in a rendered pane tree, flattened out of its overlay."""
    curves = []
    for pane in viewable.select(pn.pane.HoloViews):
        obj = pane.object
        if isinstance(obj, hv.Overlay):
            curves.extend(e for e in obj.values() if isinstance(e, hv.Curve))
        elif isinstance(obj, hv.Curve):
            curves.append(obj)
    return curves


def curves_of(overlay: hv.Overlay) -> list[hv.Curve]:
    return [e for e in overlay.values() if isinstance(e, hv.Curve)]


def plot_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "plot").kwargs


def style_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "style").kwargs


class TestXYCurveFactory(unittest.TestCase):
    """The container callback: a table in, an overlay of curves out."""

    def setUp(self):
        self.df = trace_frame(1.0)

    def test_named_columns_become_the_axes(self):
        overlay = xy_curve(x="time", y="signal")(self.df)
        (curve,) = curves_of(overlay)
        self.assertEqual([d.name for d in curve.kdims], ["time"])
        self.assertEqual(curve.vdims[0].name, "signal")
        self.assertEqual(len(curve), SAMPLES_PER_TRACE)

    def test_takes_the_object_alone(self):
        """No plot kwargs: the callback must be usable as a ResultDataSet container."""
        self.assertIsInstance(xy_curve(x="time", y="signal")(self.df), hv.Overlay)

    def test_several_y_columns_overlay_with_a_legend(self):
        overlay = xy_curve(x="time", y=["signal", "reference"])(self.df)
        curves = curves_of(overlay)
        self.assertEqual([c.label for c in curves], ["signal", "reference"])
        self.assertEqual(plot_opts(overlay)["legend_position"], "right")

    def test_single_series_gets_no_legend_position(self):
        overlay = xy_curve(x="time", y="signal")(self.df)
        self.assertNotIn("legend_position", plot_opts(overlay))

    def test_axes_inferred_from_numeric_columns(self):
        (curve,) = curves_of(xy_curve()(pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})))
        self.assertEqual([d.name for d in curve.kdims], ["a"])
        self.assertEqual(curve.vdims[0].name, "b")

    def test_named_x_infers_y(self):
        (curve,) = curves_of(xy_curve(x="time")(self.df))
        self.assertEqual(curve.vdims[0].name, "signal")

    def test_named_y_infers_x(self):
        (curve,) = curves_of(xy_curve(y="signal")(self.df))
        self.assertEqual([d.name for d in curve.kdims], ["time"])

    def test_vdims_carried_for_hover(self):
        (curve,) = curves_of(xy_curve(x="time", y="signal", vdims=["reference"])(self.df))
        self.assertEqual([d.name for d in curve.vdims], ["signal", "reference"])

    def test_a_y_column_is_not_carried_as_its_own_extra_vdim(self):
        curves = curves_of(xy_curve(x="time", y=["signal", "reference"], vdims=["signal"])(self.df))
        self.assertEqual([d.name for d in curves[0].vdims], ["signal"])
        self.assertEqual([d.name for d in curves[1].vdims], ["reference", "signal"])

    def test_axis_labels_default_to_column_names(self):
        opts = plot_opts(curves_of(xy_curve(x="time", y="signal")(self.df))[0])
        self.assertEqual((opts["xlabel"], opts["ylabel"]), ("time", "signal"))

    def test_several_series_leave_ylabel_to_holoviews(self):
        """No single column name is the right y label for an overlay."""
        opts = plot_opts(curves_of(xy_curve(x="time", y=["signal", "reference"])(self.df))[0])
        self.assertNotIn("ylabel", opts)

    def test_extra_opts_reach_holoviews(self):
        (curve,) = curves_of(xy_curve(x="time", y="signal", line_width=3)(self.df))
        self.assertEqual(style_opts(curve)["line_width"], 3)

    def test_missing_column_names_the_chart_and_what_is_available(self):
        with self.assertRaises(ValueError) as ctx:
            xy_curve(x="time", y="nope")(self.df)
        message = str(ctx.exception)
        self.assertIn("xy_curve", message)
        self.assertIn("signal", message, "the error should list the available columns")

    def test_empty_y_list_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            xy_curve(x="time", y=[])(self.df)
        self.assertIn("at least one column", str(ctx.exception))

    def test_empty_frame_with_the_columns_renders(self):
        """A run that measured nothing is an empty plot, not an exception."""
        (curve,) = curves_of(xy_curve(x="time", y="signal")(self.df.iloc[:0]))
        self.assertEqual(len(curve), 0)

    def test_non_table_rejected(self):
        with self.assertRaises(TypeError) as ctx:
            xy_curve(x="a", y="b")([1, 2, 3])
        self.assertIn("xy_curve", str(ctx.exception))


class TestSorting(unittest.TestCase):
    """A curve connects rows in order, so what order they are in is the whole point."""

    def setUp(self):
        self.df = pd.DataFrame({"t": [2.0, 0.0, 1.0], "v": [20.0, 0.0, 10.0]})

    def test_sorted_by_x_by_default(self):
        (curve,) = curves_of(xy_curve(x="t", y="v")(self.df))
        self.assertEqual(list(curve["t"]), [0.0, 1.0, 2.0])
        self.assertEqual(list(curve["v"]), [0.0, 10.0, 20.0], "rows must move together")

    def test_sort_false_keeps_row_order(self):
        """A trajectory doubles back in x, so its row order is the data."""
        (curve,) = curves_of(xy_curve(x="t", y="v", sort=False)(self.df))
        self.assertEqual(list(curve["t"]), [2.0, 0.0, 1.0])

    def test_sorting_does_not_mutate_the_stored_frame(self):
        """A sample's table is rendered repeatedly; sorting must not reorder it."""
        xy_curve(x="t", y="v")(self.df)
        self.assertEqual(list(self.df["t"]), [2.0, 0.0, 1.0])

    def test_ties_keep_their_relative_order(self):
        df = pd.DataFrame({"t": [1.0, 0.0, 1.0], "v": [10.0, 0.0, 11.0]})
        (curve,) = curves_of(xy_curve(x="t", y="v")(df))
        self.assertEqual(list(curve["v"]), [0.0, 10.0, 11.0])


class TestMarkers(unittest.TestCase):
    """Markers annotate a sparse series without becoming a series of their own."""

    def setUp(self):
        self.df = trace_frame(1.0)

    def test_off_by_default(self):
        overlay = xy_curve(x="time", y="signal")(self.df)
        self.assertEqual(len(overlay), 1)

    def test_markers_overlay_a_scatter(self):
        overlay = xy_curve(x="time", y="signal", markers=True, size=9)(self.df)
        scatters = [e for e in overlay.values() if isinstance(e, hv.Scatter)]
        self.assertEqual(len(scatters), 1)
        self.assertEqual(len(scatters[0]), SAMPLES_PER_TRACE)
        self.assertEqual(style_opts(scatters[0])["size"], 9)

    def test_markers_stay_out_of_the_legend(self):
        overlay = xy_curve(x="time", y="signal", markers=True)(self.df)
        (scatter,) = (e for e in overlay.values() if isinstance(e, hv.Scatter))
        self.assertFalse(plot_opts(scatter)["show_legend"])


class TestIndexPromotion(unittest.TestCase):
    """An xarray-derived frame keeps its x axis in the index, so it has to be reachable."""

    def test_named_index_is_plottable_by_name(self):
        (curve,) = curves_of(xy_curve(x="time", y="signal")(xarray_trace_frame(1.0)))
        self.assertEqual([d.name for d in curve.kdims], ["time"])
        self.assertEqual(len(curve), SAMPLES_PER_TRACE)

    def test_promoted_index_comes_first_so_inference_finds_it(self):
        (curve,) = curves_of(xy_curve()(xarray_trace_frame(1.0)))
        self.assertEqual([d.name for d in curve.kdims], ["time"])
        self.assertEqual(curve.vdims[0].name, "signal")

    def test_unnamed_index_is_row_position_and_is_left_alone(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        (curve,) = curves_of(xy_curve()(df))
        self.assertEqual([d.name for d in curve.kdims], ["a"])

    def test_index_name_shadowed_by_a_column_does_not_collide(self):
        """Promoting would raise; the column already provides that label."""
        df = pd.DataFrame({"time": [1.0, 2.0], "v": [3.0, 4.0]})
        df.index.name = "time"
        (curve,) = curves_of(xy_curve(x="time", y="v")(df))
        self.assertEqual(list(curve["time"]), [1.0, 2.0])

    def test_xarray_object_still_accepted_directly(self):
        t = np.linspace(0.0, 1.0, 3)
        ds = xr.Dataset({"signal": ("time", np.sin(t))}, coords={"time": t})
        (curve,) = curves_of(xy_curve(x="time", y="signal")(ds))
        self.assertEqual(len(curve), 3)


class TestXYCurveResult(unittest.TestCase):
    """The chart type: one plot per sample, tabular results only."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(TraceSweep(), "test_xy_curve", ["trace", "peak"])

    def test_one_plot_per_sample(self):
        curves = all_curves(self.res.to(XYCurveResult, x="time", y="signal"))
        self.assertEqual(len(curves), len(DURATIONS))
        for curve, duration in zip(curves, DURATIONS):
            self.assertEqual(len(curve), SAMPLES_PER_TRACE)
            self.assertAlmostEqual(curve["time"].max(), duration)

    def test_scalar_results_are_skipped(self):
        """`peak` is in the sweep; a curve over a sample's rows is undefined for it."""
        rendered = self.res.to(XYCurveResult, x="time", y="signal")
        self.assertEqual(len(all_curves(rendered)), len(DURATIONS))

    def test_several_series_per_sample(self):
        curves = all_curves(self.res.to(XYCurveResult, x="time", y=["signal", "reference"]))
        self.assertEqual(len(curves), 2 * len(DURATIONS))

    def test_options_reach_the_elements(self):
        curves = all_curves(self.res.to(XYCurveResult, x="time", y="signal", opts={"alpha": 0.3}))
        self.assertEqual(style_opts(curves[0])["alpha"], 0.3)

    def test_result_var_restriction(self):
        curves = all_curves(
            self.res.to(XYCurveResult, result_var=TraceSweep.param.trace, x="time", y="signal")
        )
        self.assertEqual(len(curves), len(DURATIONS))

    def test_bad_column_raises_rather_than_plotting_nothing(self):
        with self.assertRaises(ValueError):
            self.res.to(XYCurveResult, x="time", y="nope")

    def test_no_tabular_result_renders_nothing(self):
        self.assertIsNone(self.res.to(XYCurveResult, result_var=TraceSweep.param.peak))


class TestXYCurvePlugin(unittest.TestCase):
    """Registered as a named-only chart type, like xy_scatter."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(TraceSweep(), "test_xy_curve_plugin", ["trace", "peak"])

    def test_registered_under_its_chart_type_name(self):
        plugin = get_registry().get("xy_curve")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.backend, "holoviews")
        self.assertFalse(plugin.auto, "xy_curve must not be selected automatically")

    def test_absent_from_automatic_selection(self):
        data = self.res.to_bench_data()
        auto = [p.name for p in get_registry().select(data)]
        self.assertIn("panes", auto, "guard: automatic selection is non-empty here")
        self.assertNotIn("xy_curve", auto)

    def test_selected_by_name(self):
        data = self.res.to_bench_data()
        chosen = [p.name for p in get_registry().select(data, include=["xy_curve"])]
        self.assertEqual(chosen, ["xy_curve"])

    def test_renders_through_to_auto_by_name(self):
        res = run_sweep(TraceSweep(), "test_xy_curve_auto", ["trace", "peak"])
        rendered = res.to_auto(plot_list=["xy_curve"], x="time", y="signal")
        self.assertEqual(len(all_curves(pn.Column(*rendered))), len(DURATIONS))


class TestSpecIsPicklable(unittest.TestCase):
    """Why XYCurve is a class and not a closure."""

    def test_spec_round_trips_through_pickle(self):
        spec = xy_curve(x="time", y=["signal", "reference"], markers=True, alpha=0.5)
        restored = pickle.loads(pickle.dumps(spec))
        self.assertEqual(restored, spec)
        self.assertEqual(len(curves_of(restored(trace_frame(1.0)))), 2)

    def test_result_var_declaring_a_spec_pickles(self):
        """A declared container rides in BenchCfg, which the result cache pickles."""
        rv = pickle.loads(pickle.dumps(DeclaredCurveSweep.param.trace))
        self.assertEqual(rv.container, DeclaredCurveSweep.param.trace.container)


class TestDeclaredOnResultVar(unittest.TestCase):
    """The declarative route: the spec on the result var, rendered in place."""

    def test_panes_pass_renders_the_curve(self):
        res = run_sweep(DeclaredCurveSweep(), "test_xy_curve_declared", ["trace"])
        curves = all_curves(res.to_auto(plot_list=["panes"]))
        self.assertEqual(len(curves), len(DURATIONS))
        self.assertEqual([d.name for d in curves[0].kdims], ["time"])


if __name__ == "__main__":
    unittest.main()
