"""Tests for xy_histogram and xy_hexbin — the two intra-sample density charts.

Both live here because they answer the same question about one sample's rows
("where is the mass?") in one and two dimensions, and share their fixtures.
"""

import pickle
import unittest

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
import pytest

import bencher as bn
from bencher.plugins import get_registry
from bencher.results.holoview_results.holoview_result import DEFAULT_PLOT_SIZE
from bencher.results.holoview_results.xy_hexbin_result import XYHexbinResult, xy_hexbin
from bencher.results.holoview_results.xy_histogram_result import XYHistogramResult, xy_histogram
from test.helpers import run_cfg_with

SPREADS = [1.0, 2.0]
ROWS_PER_SAMPLE = 200


def cloud_frame(spread: float) -> pd.DataFrame:
    """A deterministic cloud whose rows are the measurement."""
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "error_mm": rng.normal(0.0, spread, ROWS_PER_SAMPLE),
            "baseline_mm": rng.normal(1.0, spread, ROWS_PER_SAMPLE),
        }
    )


class CloudSweep(bn.ParametrizedSweep):
    """Each sample measures a cloud of points, plus one scalar."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)

    cloud = bn.ResultDataSet(doc="measured points, one row each")
    peak = bn.ResultFloat(units="mm", doc="a scalar that is not a distribution")

    def benchmark(self):
        self.cloud = bn.ResultDataSet(cloud_frame(self.spread))
        self.peak = self.spread


class DeclaredHistogramSweep(bn.ParametrizedSweep):
    """The spec lives on the result var, so the distribution renders in place."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    cloud = bn.ResultDataSet(container=xy_histogram("error_mm", bins=8))

    def benchmark(self):
        self.cloud = bn.ResultDataSet(cloud_frame(self.spread))


class DeclaredHexbinSweep(bn.ParametrizedSweep):
    """Same, for the two-dimensional density."""

    spread = bn.FloatSweep(default=1.0, bounds=[1.0, 2.0], samples=2)
    cloud = bn.ResultDataSet(container=xy_hexbin(x="error_mm", y="baseline_mm", data_aspect=1))

    def benchmark(self):
        self.cloud = bn.ResultDataSet(cloud_frame(self.spread))


def run_sweep(worker: bn.ParametrizedSweep, name: str, result_vars: list[str]):
    bench = bn.Bench(name, worker, run_cfg=run_cfg_with(1))
    return bench.plot_sweep(
        name, input_vars=["spread"], result_vars=result_vars, plot_callbacks=False
    )


def elements_of(viewable: pn.viewable.Viewable, kind: type) -> list:
    """Every element of *kind* in a rendered pane tree, flattened out of overlays."""
    found = []
    for pane in viewable.select(pn.pane.HoloViews):
        obj = pane.object
        if isinstance(obj, hv.Overlay):
            found.extend(e for e in obj.values() if isinstance(e, kind))
        elif isinstance(obj, kind):
            found.append(obj)
    return found


def only(overlay: hv.Overlay):
    """The single element of a one-series overlay."""
    (element,) = overlay.values()
    return element


def first(overlay: hv.Overlay):
    """The first element of a multi-series overlay."""
    return next(iter(overlay.values()))


def plot_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "plot").kwargs


def style_opts(element) -> dict:
    return hv.Store.lookup_options("bokeh", element, "style").kwargs


class TestXYHistogramFactory(unittest.TestCase):
    """The container callback: a table in, an overlay of histograms out."""

    def setUp(self):
        self.df = cloud_frame(1.0)

    def test_named_column_is_binned(self):
        element = only(xy_histogram("error_mm", bins=10)(self.df))
        assert isinstance(element, hv.Histogram)
        assert len(element) == 10
        assert sum(element["count"]) == ROWS_PER_SAMPLE, "every row must be counted"

    def test_takes_the_object_alone(self):
        """No plot kwargs: the callback must be usable as a ResultDataSet container."""
        assert isinstance(xy_histogram("error_mm")(self.df), hv.Overlay)

    def test_bins_are_configurable(self):
        assert len(only(xy_histogram("error_mm", bins=5)(self.df))) == 5

    def test_column_defaults_to_every_numeric_column(self):
        overlay = xy_histogram()(self.df)
        assert [e.label for e in overlay.values()] == ["error_mm", "baseline_mm"]

    def test_several_columns_overlay_with_a_legend(self):
        overlay = xy_histogram(["error_mm", "baseline_mm"])(self.df)
        assert len(overlay) == 2
        assert plot_opts(overlay)["legend_position"] == "right"

    def test_overlaid_distributions_share_one_bin_range(self):
        """Two distributions binned to their own spans would not be comparable."""
        overlay = xy_histogram(["error_mm", "baseline_mm"], bins=10)(self.df)
        ranges = {tuple(e.range("value")) for e in overlay.values()}
        assert len(ranges) == 1

    def test_overlaid_distributions_are_translucent(self):
        """An opaque histogram drawn on top would hide the one underneath."""
        overlay = xy_histogram(["error_mm", "baseline_mm"])(self.df)
        assert style_opts(first(overlay))["alpha"] < 1.0

    def test_a_single_distribution_is_not_made_translucent(self):
        assert style_opts(only(xy_histogram("error_mm")(self.df))).get("alpha") is None

    def test_explicit_bin_range_is_honoured(self):
        element = only(xy_histogram("error_mm", bins=4, bin_range=(-1.0, 1.0))(self.df))
        low, high = element.range("error_mm")
        self.assertAlmostEqual(low, -1.0)
        self.assertAlmostEqual(high, 1.0)

    def test_density_normalises_and_relabels_the_y_axis(self):
        element = only(xy_histogram("error_mm", density=True)(self.df))
        assert [d.name for d in element.vdims] == ["density"]
        assert plot_opts(element)["ylabel"] == "density"

    def test_counting_labels_the_y_axis_count(self):
        element = only(xy_histogram("error_mm")(self.df))
        assert plot_opts(element)["ylabel"] == "count"

    def test_extra_opts_reach_holoviews(self):
        element = only(xy_histogram("error_mm", alpha=0.2)(self.df))
        assert style_opts(element)["alpha"] == 0.2

    def test_explicit_labels_win_over_the_derived_defaults(self):
        """count/density and the column name are defaults, not overrides."""
        spec = xy_histogram("error_mm", density=True, xlabel="error [mm]", ylabel="probability")
        opts = plot_opts(only(spec(self.df)))
        assert (opts["xlabel"], opts["ylabel"]) == ("error [mm]", "probability")

    def test_explicit_ylabel_survives_an_overlay(self):
        overlay = xy_histogram(["error_mm", "baseline_mm"], ylabel="fraction")(self.df)
        assert plot_opts(first(overlay))["ylabel"] == "fraction"

    def test_opts_override_the_overlay_translucency(self):
        """`opts` is applied last, so it beats the alpha the overlay would pick."""
        overlay = xy_histogram(["error_mm", "baseline_mm"], alpha=1.0)(self.df)
        assert style_opts(first(overlay))["alpha"] == 1.0

    def test_missing_column_names_the_chart_and_what_is_available(self):
        with pytest.raises(ValueError) as ctx:
            xy_histogram("nope")(self.df)
        message = str(ctx.value)
        assert "xy_histogram" in message
        assert "error_mm" in message, "the error should list the available columns"

    def test_empty_column_list_rejected(self):
        with pytest.raises(ValueError) as ctx:
            xy_histogram([])(self.df)
        assert "at least one column" in str(ctx.value)

    def test_frame_with_no_numeric_column_rejected(self):
        with pytest.raises(ValueError) as ctx:
            xy_histogram()(pd.DataFrame({"label": ["a", "b"]}))
        assert "column=" in str(ctx.value)

    def test_non_table_rejected(self):
        with pytest.raises(TypeError) as ctx:
            xy_histogram("a")([1, 2, 3])
        assert "xy_histogram" in str(ctx.value)


class TestHistogramMissingData(unittest.TestCase):
    """numpy cannot bin an empty array; a run that measured nothing is not a crash."""

    def test_empty_frame_gives_empty_bins(self):
        element = only(xy_histogram("v", bins=6)(pd.DataFrame({"v": []}, dtype=float)))
        assert len(element) == 6
        assert set(element["count"]) == {0.0}

    def test_all_nan_column_gives_empty_bins(self):
        """NaN is how bencher marks a sample missing, not a value to bin."""
        element = only(xy_histogram("v", bins=6)(pd.DataFrame({"v": [np.nan] * 4})))
        assert set(element["count"]) == {0.0}

    def test_nan_rows_are_dropped_not_counted(self):
        element = only(xy_histogram("v")(pd.DataFrame({"v": [1.0, np.nan, 2.0, 2.0]})))
        assert sum(element["count"]) == 3


class TestXYHexbinFactory(unittest.TestCase):
    """The container callback: a table in, hexagonally-binned density out."""

    def setUp(self):
        self.df = cloud_frame(1.0)

    def test_named_columns_become_the_axes(self):
        tiles = xy_hexbin(x="error_mm", y="baseline_mm")(self.df)
        assert isinstance(tiles, hv.HexTiles)
        assert [d.name for d in tiles.kdims] == ["error_mm", "baseline_mm"]
        assert len(tiles) == ROWS_PER_SAMPLE

    def test_takes_the_object_alone(self):
        assert isinstance(xy_hexbin(x="error_mm", y="baseline_mm")(self.df), hv.HexTiles)

    def test_gridsize_and_cmap_reach_the_element(self):
        tiles = xy_hexbin(x="error_mm", y="baseline_mm", gridsize=13, cmap="magma")(self.df)
        assert plot_opts(tiles)["gridsize"] == 13
        assert style_opts(tiles)["cmap"] == "magma"

    def test_colorbar_on_by_default(self):
        """A density plot without one shows shape but no magnitude."""
        assert plot_opts(xy_hexbin(x="error_mm", y="baseline_mm")(self.df))["colorbar"]
        off = xy_hexbin(x="error_mm", y="baseline_mm", colorbar=False)(self.df)
        assert not plot_opts(off)["colorbar"]

    def test_min_count_is_opt_in(self):
        assert "min_count" not in plot_opts(xy_hexbin(x="error_mm", y="baseline_mm")(self.df))
        tiles = xy_hexbin(x="error_mm", y="baseline_mm", min_count=1)(self.df)
        assert plot_opts(tiles)["min_count"] == 1

    def test_data_aspect_is_opt_in(self):
        assert "data_aspect" not in plot_opts(xy_hexbin(x="error_mm", y="baseline_mm")(self.df))
        tiles = xy_hexbin(x="error_mm", y="baseline_mm", data_aspect=1)(self.df)
        assert plot_opts(tiles)["data_aspect"] == 1

    def test_axes_inferred_from_numeric_columns(self):
        tiles = xy_hexbin()(self.df)
        assert [d.name for d in tiles.kdims] == ["error_mm", "baseline_mm"]

    def test_axis_labels_default_to_column_names(self):
        opts = plot_opts(xy_hexbin(x="error_mm", y="baseline_mm")(self.df))
        assert (opts["xlabel"], opts["ylabel"]) == ("error_mm", "baseline_mm")

    def test_explicit_labels_win_over_the_column_names(self):
        opts = plot_opts(
            xy_hexbin(x="error_mm", y="baseline_mm", xlabel="error [mm]", ylabel="baseline [mm]")(
                self.df
            )
        )
        assert (opts["xlabel"], opts["ylabel"]) == ("error [mm]", "baseline [mm]")

    def test_opts_are_applied_after_the_chart_options(self):
        """`opts` goes on last, so an unexposed holoviews keyword is never dropped."""
        tiles = xy_hexbin(x="error_mm", y="baseline_mm", gridsize=13, alpha=0.4)(self.df)
        assert style_opts(tiles)["alpha"] == 0.4
        assert plot_opts(tiles)["gridsize"] == 13, "the chart option must still apply"

    def test_missing_column_names_the_chart(self):
        with pytest.raises(ValueError) as ctx:
            xy_hexbin(x="error_mm", y="nope")(self.df)
        assert "xy_hexbin" in str(ctx.value)

    def test_empty_frame_with_the_columns_renders(self):
        tiles = xy_hexbin(x="error_mm", y="baseline_mm")(self.df.iloc[:0])
        assert len(tiles) == 0

    def test_non_table_rejected(self):
        with pytest.raises(TypeError) as ctx:
            xy_hexbin(x="a", y="b")([1, 2, 3])
        assert "xy_hexbin" in str(ctx.value)

    def test_hextiles_carries_the_shared_default_size(self):
        """HexTiles was not in DEFAULT_SIZED_ELEMENTS, so it fell back to a smaller figure."""
        assert plot_opts(xy_hexbin()(self.df))["width"] == DEFAULT_PLOT_SIZE


class TestChartTypes(unittest.TestCase):
    """Both as report-level chart types: one plot per sample, tabular results only."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(CloudSweep(), "test_xy_distribution", ["cloud", "peak"])

    def test_histogram_one_plot_per_sample(self):
        found = elements_of(self.res.to(XYHistogramResult, column="error_mm"), hv.Histogram)
        assert len(found) == len(SPREADS)
        for element in found:
            assert sum(element["count"]) == ROWS_PER_SAMPLE

    def test_hexbin_one_plot_per_sample(self):
        found = elements_of(self.res.to(XYHexbinResult, x="error_mm", y="baseline_mm"), hv.HexTiles)
        assert len(found) == len(SPREADS)

    def test_histogram_options_reach_the_elements(self):
        found = elements_of(
            self.res.to(XYHistogramResult, column="error_mm", bins=7, density=True), hv.Histogram
        )
        assert len(found[0]) == 7
        assert [d.name for d in found[0].vdims] == ["density"]

    def test_hexbin_options_reach_the_elements(self):
        found = elements_of(
            self.res.to(XYHexbinResult, x="error_mm", y="baseline_mm", gridsize=11, data_aspect=1),
            hv.HexTiles,
        )
        assert plot_opts(found[0])["gridsize"] == 11
        assert plot_opts(found[0])["data_aspect"] == 1

    def test_scalar_results_are_skipped(self):
        """`peak` is in the sweep; a distribution of a sample's rows is undefined for it."""
        assert self.res.to(XYHistogramResult, result_var=CloudSweep.param.peak) is None
        assert self.res.to(XYHexbinResult, result_var=CloudSweep.param.peak) is None

    def test_bad_column_raises_rather_than_plotting_nothing(self):
        with pytest.raises(ValueError):
            self.res.to(XYHistogramResult, column="nope")
        with pytest.raises(ValueError):
            self.res.to(XYHexbinResult, x="error_mm", y="nope")


class TestPlugins(unittest.TestCase):
    """Registered as named-only chart types, like xy_scatter and xy_curve."""

    @classmethod
    def setUpClass(cls):
        cls.res = run_sweep(CloudSweep(), "test_xy_distribution_plugin", ["cloud", "peak"])

    def test_registered_under_their_chart_type_names(self):
        for name in ("xy_histogram", "xy_hexbin"):
            plugin = get_registry().get(name)
            assert plugin is not None, name
            assert plugin.backend == "holoviews", name
            assert not plugin.auto, f"{name} must not be selected automatically"

    def test_absent_from_automatic_selection(self):
        auto = [p.name for p in get_registry().select(self.res.to_bench_data())]
        assert "panes" in auto, "guard: automatic selection is non-empty here"
        assert "xy_histogram" not in auto
        assert "xy_hexbin" not in auto

    def test_histogram_renders_through_to_auto_by_name(self):
        res = run_sweep(CloudSweep(), "test_xy_histogram_auto", ["cloud", "peak"])
        rendered = res.to_auto(plot_list=["xy_histogram"], column="error_mm")
        found = elements_of(pn.Column(*rendered), hv.Histogram)
        assert len(found) == len(SPREADS)

    def test_hexbin_renders_through_to_auto_by_name(self):
        res = run_sweep(CloudSweep(), "test_xy_hexbin_auto", ["cloud", "peak"])
        rendered = res.to_auto(plot_list=["xy_hexbin"], x="error_mm", y="baseline_mm")
        found = elements_of(pn.Column(*rendered), hv.HexTiles)
        assert len(found) == len(SPREADS)


class TestSpecsArePicklable(unittest.TestCase):
    """Why these are classes and not closures: they ride in BenchCfg, which is pickled."""

    def test_histogram_spec_round_trips(self):
        spec = xy_histogram(["error_mm", "baseline_mm"], bins=12, density=True, alpha=0.4)
        restored = pickle.loads(pickle.dumps(spec))
        assert restored == spec
        assert len(restored(cloud_frame(1.0))) == 2

    def test_hexbin_spec_round_trips(self):
        spec = xy_hexbin(x="error_mm", y="baseline_mm", gridsize=9, data_aspect=1)
        restored = pickle.loads(pickle.dumps(spec))
        assert restored == spec
        assert isinstance(restored(cloud_frame(1.0)), hv.HexTiles)

    def test_result_vars_declaring_specs_pickle(self):
        for cls in (DeclaredHistogramSweep, DeclaredHexbinSweep):
            rv = pickle.loads(pickle.dumps(cls.param.cloud))
            assert rv.container == cls.param.cloud.container, cls.__name__


class TestDeclaredOnResultVar(unittest.TestCase):
    """The declarative route: the spec on the result var, rendered in place."""

    def test_histogram_renders_through_the_panes_pass(self):
        res = run_sweep(DeclaredHistogramSweep(), "test_xy_histogram_declared", ["cloud"])
        found = elements_of(res.to_auto(plot_list=["panes"]), hv.Histogram)
        assert len(found) == len(SPREADS)
        assert len(found[0]) == 8, "the declared bin count must survive the round trip"

    def test_hexbin_renders_through_the_panes_pass(self):
        res = run_sweep(DeclaredHexbinSweep(), "test_xy_hexbin_declared", ["cloud"])
        found = elements_of(res.to_auto(plot_list=["panes"]), hv.HexTiles)
        assert len(found) == len(SPREADS)
        assert plot_opts(found[0])["data_aspect"] == 1


if __name__ == "__main__":
    unittest.main()
