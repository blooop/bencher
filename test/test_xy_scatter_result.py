"""Tests for XYScatterResult / xy_scatter (bencher/results/holoview_results/xy_scatter_result.py)."""

import pickle
import unittest
from datetime import datetime, timedelta

import holoviews as hv
import pandas as pd
import panel as pn
import xarray as xr

import bencher as bn
from bencher.plugins import get_registry
from bencher.results.holoview_results.xy_scatter_result import XYScatterResult, xy_scatter
from test.helpers import run_cfg_with

SPREADS = [1.0, 2.0]
POINTS_PER_SAMPLE = 5


def cloud_frame(spread: float) -> pd.DataFrame:
    """A deterministic cloud: rows are the measurement, columns are the axes."""
    return pd.DataFrame(
        {
            "index": list(range(POINTS_PER_SAMPLE)),
            "dx_mm": [spread * i for i in range(POINTS_PER_SAMPLE)],
            "dy_mm": [-spread * i for i in range(POINTS_PER_SAMPLE)],
        }
    )


class CloudSweep(bn.ParametrizedSweep):
    """Each sample measures a cloud of points, plus one scalar."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)

    cloud = bn.ResultDataSet(doc="measured points, one row each")
    peak = bn.ResultFloat(units="mm", doc="a scalar that is not a scatter")

    def benchmark(self):
        self.cloud = bn.ResultDataSet(cloud_frame(self.spread))
        self.peak = self.spread * POINTS_PER_SAMPLE


class DeclaredScatterSweep(bn.ParametrizedSweep):
    """The spec lives on the result var, so the cloud renders with the other results."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    cloud = bn.ResultDataSet(container=xy_scatter(x="dx_mm", y="dy_mm", data_aspect=1))

    def benchmark(self):
        self.cloud = bn.ResultDataSet(cloud_frame(self.spread))


def run_sweep(worker: bn.ParametrizedSweep, name: str, result_vars: list[str]):
    bench = bn.Bench(name, worker, run_cfg=run_cfg_with(1))
    return bench.plot_sweep(
        name, input_vars=["spread"], result_vars=result_vars, plot_callbacks=False
    )


def run_tagged_cloud(spread: float, run_id: int) -> pd.DataFrame:
    """A cloud offset by its run, so a rendered plot names the run it came from."""
    return pd.DataFrame(
        {
            "dx_mm": [spread * i + RUN_OFFSET * run_id for i in range(POINTS_PER_SAMPLE)],
            "dy_mm": [-spread * i for i in range(POINTS_PER_SAMPLE)],
        }
    )


RUN_OFFSET = 100.0
OVER_TIME_RUNS = 3


class OverTimeCloudSweep(bn.ParametrizedSweep):
    """A declared scatter, to be run repeatedly against one history."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    cloud = bn.ResultDataSet(container=xy_scatter(x="dx_mm", y="dy_mm"))
    peak = bn.ResultFloat(units="mm", doc="a scalar, which does keep history")

    run_id = 0

    def benchmark(self):
        self.cloud = bn.ResultDataSet(run_tagged_cloud(self.spread, self.run_id))
        self.peak = self.spread + self.run_id


def run_sweep_over_time(worker: bn.ParametrizedSweep, name: str) -> bn.BenchResult:
    """Run one sweep repeatedly against a single history, as a nightly rig does.

    Only the first run clears the history, so from the second run on the rendered
    dataset carries the earlier events on its over_time dimension.
    """
    run_cfg = run_cfg_with(1)
    run_cfg.over_time = True
    run_cfg.auto_plot = False
    bench = bn.Bench(name, worker)
    base_time = datetime(2000, 1, 1)
    res = None
    for i in range(OVER_TIME_RUNS):
        worker.run_id = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            name,
            input_vars=["spread"],
            result_vars=["cloud", "peak"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            plot_callbacks=False,
        )
    return res


def all_points(viewable: pn.viewable.Viewable) -> list[hv.Points]:
    """Every hv.Points element in a rendered pane tree."""
    return [
        pane.object
        for pane in viewable.select(pn.pane.HoloViews)
        if isinstance(pane.object, hv.Points)
    ]


def plot_opts(points: hv.Points) -> dict:
    return hv.Store.lookup_options("bokeh", points, "plot").kwargs


def style_opts(points: hv.Points) -> dict:
    return hv.Store.lookup_options("bokeh", points, "style").kwargs


class TestXYScatterFactory(unittest.TestCase):
    """The container callback: a table in, an hv.Points out."""

    def setUp(self):
        self.df = cloud_frame(1.0)

    def test_named_columns_become_the_axes(self):
        points = xy_scatter(x="dx_mm", y="dy_mm")(self.df)
        self.assertIsInstance(points, hv.Points)
        self.assertEqual([d.name for d in points.kdims], ["dx_mm", "dy_mm"])
        self.assertEqual(len(points), POINTS_PER_SAMPLE)

    def test_takes_the_object_alone(self):
        """No plot kwargs: the callback must be usable as a ResultDataSet container."""
        self.assertIsInstance(xy_scatter(x="dx_mm", y="dy_mm")(self.df), hv.Points)

    def test_color_column_becomes_a_value_dim(self):
        points = xy_scatter(x="dx_mm", y="dy_mm", color="index")(self.df)
        self.assertEqual([d.name for d in points.vdims], ["index"])
        self.assertEqual(style_opts(points)["color"], "index")
        self.assertTrue(plot_opts(points)["colorbar"])

    def test_vdims_carried_for_hover(self):
        points = xy_scatter(x="dx_mm", y="dy_mm", vdims=["index"])(self.df)
        self.assertEqual([d.name for d in points.vdims], ["index"])

    def test_data_aspect_is_opt_in(self):
        self.assertNotIn("data_aspect", plot_opts(xy_scatter(x="dx_mm", y="dy_mm")(self.df)))
        squared = xy_scatter(x="dx_mm", y="dy_mm", data_aspect=1)(self.df)
        self.assertEqual(plot_opts(squared)["data_aspect"], 1)

    def test_axis_labels_default_to_column_names(self):
        opts = plot_opts(xy_scatter(x="dx_mm", y="dy_mm")(self.df))
        self.assertEqual((opts["xlabel"], opts["ylabel"]), ("dx_mm", "dy_mm"))
        labelled = xy_scatter(x="dx_mm", y="dy_mm", xlabel="dx [mm]", ylabel="dy [mm]")(self.df)
        self.assertEqual(plot_opts(labelled)["xlabel"], "dx [mm]")

    def test_extra_opts_reach_holoviews(self):
        points = xy_scatter(x="dx_mm", y="dy_mm", alpha=0.25)(self.df)
        self.assertEqual(style_opts(points)["alpha"], 0.25)

    def test_missing_column_names_what_is_available(self):
        with self.assertRaises(ValueError) as ctx:
            xy_scatter(x="dx_mm", y="nope")(self.df)
        message = str(ctx.exception)
        self.assertIn("nope", message)
        self.assertIn("dy_mm", message, "the error should list the available columns")

    def test_missing_color_column_raises(self):
        with self.assertRaises(ValueError):
            xy_scatter(x="dx_mm", y="dy_mm", color="nope")(self.df)

    def test_axes_inferred_from_numeric_columns(self):
        points = xy_scatter()(pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}))
        self.assertEqual([d.name for d in points.kdims], ["a", "b"])

    def test_one_named_axis_infers_the_other(self):
        points = xy_scatter(y="dy_mm")(self.df)
        self.assertEqual([d.name for d in points.kdims], ["index", "dy_mm"])

    def test_inference_needs_two_numeric_columns(self):
        with self.assertRaises(ValueError) as ctx:
            xy_scatter()(pd.DataFrame({"a": [1.0], "label": ["x"]}))
        self.assertIn("x= and y=", str(ctx.exception))

    def test_empty_frame_with_the_columns_renders(self):
        """A run that measured nothing is an empty plot, not an exception."""
        points = xy_scatter(x="dx_mm", y="dy_mm")(self.df.iloc[:0])
        self.assertEqual(len(points), 0)

    def test_xarray_dataset_accepted(self):
        ds = xr.Dataset({"dy_mm": ("dx_mm", [1.0, 2.0, 3.0])}, coords={"dx_mm": [0.0, 1.0, 2.0]})
        points = xy_scatter(x="dx_mm", y="dy_mm")(ds)
        self.assertEqual(len(points), 3)

    def test_non_table_rejected(self):
        with self.assertRaises(TypeError) as ctx:
            xy_scatter(x="a", y="b")([1, 2, 3])
        self.assertIn("list", str(ctx.exception))


class TestNonStringColumnLabels(unittest.TestCase):
    """A column label is only a string by convention; lookups must use the real label."""

    def setUp(self):
        self.df = pd.DataFrame({0: [1.0, 2.0], 1: [3.0, 4.0], 2: [5.0, 6.0]})

    def test_integer_labels_inferred(self):
        points = xy_scatter()(self.df)
        self.assertEqual([d.name for d in points.kdims], ["0", "1"])
        self.assertEqual(len(points), 2)

    def test_integer_labels_named_explicitly(self):
        points = xy_scatter(x=2, y=0)(self.df)
        self.assertEqual([d.name for d in points.kdims], ["2", "0"])
        self.assertEqual(list(points["2"]), [5.0, 6.0])

    def test_integer_label_as_colour_and_vdim(self):
        points = xy_scatter(x=0, y=1, color=2)(self.df)
        self.assertEqual([d.name for d in points.vdims], ["2"])
        self.assertEqual(style_opts(points)["color"], "2")

    def test_one_named_integer_axis_infers_the_other(self):
        points = xy_scatter(y=1)(self.df)
        self.assertEqual([d.name for d in points.kdims], ["0", "1"])

    def test_missing_integer_label_raises(self):
        with self.assertRaises(ValueError) as ctx:
            xy_scatter(x=0, y=9)(self.df)
        self.assertIn("9", str(ctx.exception))

    def test_timestamp_labels_are_usable(self):
        stamps = pd.to_datetime(["2024-01-01", "2024-01-02"])
        df = pd.DataFrame({stamps[0]: [1.0, 2.0], stamps[1]: [3.0, 4.0]})
        points = xy_scatter(x=stamps[0], y=stamps[1])(df)
        self.assertEqual([d.name for d in points.kdims], [str(stamps[0]), str(stamps[1])])

    def test_labels_colliding_once_stringified_raise(self):
        df = pd.DataFrame({0: [1.0, 2.0], "0": [3.0, 4.0]})
        with self.assertRaises(ValueError) as ctx:
            xy_scatter(x=0, y="0")(df)
        self.assertIn("collide", str(ctx.exception))


class TestXYScatterResult(unittest.TestCase):
    """The chart type: one scatter per sample, tabular results only."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(CloudSweep(), "test_xy_scatter", ["cloud", "peak"])

    def test_one_plot_per_sample(self):
        points = all_points(self.res.to(XYScatterResult, x="dx_mm", y="dy_mm"))
        self.assertEqual(len(points), len(SPREADS))
        for element, spread in zip(points, SPREADS):
            self.assertEqual(len(element), POINTS_PER_SAMPLE)
            self.assertEqual(element["dx_mm"].max(), spread * (POINTS_PER_SAMPLE - 1))

    def test_scalar_results_are_skipped(self):
        """`peak` is in the sweep; a scatter of two columns is undefined for it."""
        rendered = self.res.to(XYScatterResult, x="dx_mm", y="dy_mm")
        self.assertEqual(len(all_points(rendered)), len(SPREADS))

    def test_options_reach_the_elements(self):
        points = all_points(
            self.res.to(XYScatterResult, x="dx_mm", y="dy_mm", color="index", data_aspect=1)
        )
        self.assertEqual(plot_opts(points[0])["data_aspect"], 1)
        self.assertEqual(style_opts(points[0])["color"], "index")

    def test_result_var_restriction(self):
        points = all_points(
            self.res.to(
                XYScatterResult,
                result_var=CloudSweep.param.cloud,
                x="dx_mm",
                y="dy_mm",
            )
        )
        self.assertEqual(len(points), len(SPREADS))

    def test_bad_column_raises_rather_than_plotting_nothing(self):
        with self.assertRaises(ValueError):
            self.res.to(XYScatterResult, x="dx_mm", y="nope")

    def test_no_tabular_result_renders_nothing(self):
        self.assertIsNone(self.res.to(XYScatterResult, result_var=CloudSweep.param.peak))


class TestXYScatterPlugin(unittest.TestCase):
    """Registered as a named-only chart type, like dataset/table/rerun."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(CloudSweep(), "test_xy_scatter_plugin", ["cloud", "peak"])

    def test_registered_under_its_chart_type_name(self):
        plugin = get_registry().get("xy_scatter")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.backend, "holoviews")
        self.assertFalse(plugin.auto, "xy_scatter must not be selected automatically")

    def test_absent_from_automatic_selection(self):
        data = self.res.to_bench_data()
        auto = [p.name for p in get_registry().select(data)]
        self.assertIn("panes", auto, "guard: automatic selection is non-empty here")
        self.assertNotIn("xy_scatter", auto)

    def test_selected_by_name(self):
        data = self.res.to_bench_data()
        chosen = [p.name for p in get_registry().select(data, include=["xy_scatter"])]
        self.assertEqual(chosen, ["xy_scatter"])

    def test_renders_through_to_auto_by_name(self):
        res = run_sweep(CloudSweep(), "test_xy_scatter_auto", ["cloud", "peak"])
        rendered = res.to_auto(plot_list=["xy_scatter"], x="dx_mm", y="dy_mm")
        self.assertEqual(len(all_points(pn.Column(*rendered))), len(SPREADS))


class TestSpecIsPicklable(unittest.TestCase):
    """Why XYScatter is a class and not a closure."""

    def test_spec_round_trips_through_pickle(self):
        spec = xy_scatter(x="dx_mm", y="dy_mm", color="index", data_aspect=1, alpha=0.5)
        restored = pickle.loads(pickle.dumps(spec))
        self.assertEqual(restored, spec)
        points = restored(cloud_frame(1.0))
        self.assertEqual([d.name for d in points.kdims], ["dx_mm", "dy_mm"])

    def test_result_var_declaring_a_spec_pickles(self):
        """A declared container rides in BenchCfg, which the result cache pickles."""
        rv = pickle.loads(pickle.dumps(DeclaredScatterSweep.param.cloud))
        self.assertEqual(rv.container, DeclaredScatterSweep.param.cloud.container)


class TestDeclaredOnResultVar(unittest.TestCase):
    """The declarative route: the spec on the result var, rendered in place."""

    def test_default_output_replaces_the_raw_table_with_the_scatter(self):
        res = run_sweep(DeclaredScatterSweep(), "test_xy_scatter_default", ["cloud"])
        rendered = pn.Column(*res.to_auto())
        self.assertEqual(len(all_points(rendered)), len(SPREADS))
        self.assertEqual(rendered.select(pn.pane.DataFrame), [])

    def test_panes_pass_renders_the_scatter(self):
        res = run_sweep(DeclaredScatterSweep(), "test_xy_scatter_declared", ["cloud"])
        points = all_points(res.to_auto(plot_list=["panes"]))
        self.assertEqual(len(points), len(SPREADS))
        self.assertEqual([d.name for d in points[0].kdims], ["dx_mm", "dy_mm"])
        self.assertEqual(plot_opts(points[0])["data_aspect"], 1)


class TestOverTimeHistory(unittest.TestCase):
    """A cloud history has to render every run, not only the latest one.

    Cells are blob paths since plan 22, meaningful in any run, so the events merged
    in from history render alongside the current one (D4).  Before that, a
    ResultDataSet cell held an index into dataset_list — rebuilt from whichever run
    was rendering — so the render was forcibly restricted to the current event.
    """

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep_over_time(OverTimeCloudSweep(), "test_xy_scatter_over_time")

    def assert_every_run(self, points: list[hv.Points]) -> None:
        """One scatter per (sample, event): samples peeled outermost, time innermost."""
        self.assertEqual(len(points), len(SPREADS) * OVER_TIME_RUNS)
        expected = [(spread, run) for spread in SPREADS for run in range(OVER_TIME_RUNS)]
        for element, (spread, run) in zip(points, expected):
            self.assertEqual(len(element), POINTS_PER_SAMPLE)
            self.assertAlmostEqual(element["dx_mm"].min(), RUN_OFFSET * run, places=6)
            self.assertAlmostEqual(
                element["dx_mm"].max(),
                spread * (POINTS_PER_SAMPLE - 1) + RUN_OFFSET * run,
                places=6,
            )

    def test_history_accumulated(self):
        """Guard on the fixture: with a single event there is no regression to catch."""
        self.assertEqual(self.res.to_dataset().sizes["over_time"], OVER_TIME_RUNS)

    def test_declared_spec_renders_every_run(self):
        self.assert_every_run(all_points(self.res.to_auto(plot_list=["panes"])))

    def test_chart_type_renders_every_run(self):
        rendered = self.res.to(XYScatterResult, x="dx_mm", y="dy_mm")
        self.assert_every_run(all_points(rendered))

    def test_named_chart_type_renders_every_run(self):
        rendered = self.res.to_auto(plot_list=["xy_scatter"], x="dx_mm", y="dy_mm")
        self.assert_every_run(all_points(pn.Column(*rendered)))

    def test_scalar_results_keep_their_history(self):
        """Rendering the current cloud must not cost the metrics their over_time series."""
        peak = self.res.to_dataset()["peak"]
        self.assertEqual(peak.sizes["over_time"], OVER_TIME_RUNS)
        for run in range(OVER_TIME_RUNS):
            observed = peak.isel(over_time=run).sel(spread=SPREADS[0]).values.squeeze()
            self.assertAlmostEqual(float(observed), SPREADS[0] + run)


if __name__ == "__main__":
    unittest.main()
