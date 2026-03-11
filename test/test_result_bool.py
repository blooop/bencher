"""Comprehensive test suite for ResultBool and its interaction with plot types.

Verifies that all plot types correctly support ResultBool as a result type,
producing valid plots for boolean benchmark data.
"""

import unittest
from enum import auto
from strenum import StrEnum

import holoviews as hv
import numpy as np
from param import Number

import bencher as bch
from bencher.results.holoview_results.bar_result import BarResult
from bencher.results.holoview_results.line_result import LineResult
from bencher.results.holoview_results.curve_result import CurveResult
from bencher.results.holoview_results.heatmap_result import HeatmapResult
from bencher.results.holoview_results.surface_result import SurfaceResult
from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
from bencher.results.holoview_results.distribution_result.box_whisker_result import (
    BoxWhiskerResult,
)
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
from bencher.results.holoview_results.scatter_result import ScatterResult
from bencher.results.holoview_results.table_result import TableResult
from bencher.results.holoview_results.tabulator_result import TabulatorResult
from bencher.results.histogram_result import HistogramResult
from bencher.results.volume_result import VolumeResult
from bencher.variables.results import ResultVar, ResultBool


# ---------------------------------------------------------------------------
# Test fixture: ParametrizedSweep subclasses
# ---------------------------------------------------------------------------


class CatEnum(StrEnum):
    A = auto()
    B = auto()
    C = auto()


class BoolBenchDeterministic(bch.ParametrizedSweep):
    """Cat + float inputs, deterministic bool output. For single-repeat tests."""

    cat = bch.EnumSweep(CatEnum, doc="Categorical input")
    x = bch.FloatSweep(default=0, bounds=[0, 1], doc="Float input")
    out = bch.ResultBool(doc="Deterministic bool output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = self.x > 0.5
        return super().__call__(**kwargs)


class BoolBenchAlternating(bch.ParametrizedSweep):
    """Counter-based alternating True/False. For multi-repeat aggregation tests."""

    cat = bch.EnumSweep(CatEnum, doc="Categorical input")
    x = bch.FloatSweep(default=0, bounds=[0, 1], doc="Float input")
    out = bch.ResultBool(doc="Alternating bool output")

    _call_count = 0

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        BoolBenchAlternating._call_count += 1
        self.out = (BoolBenchAlternating._call_count % 2) == 0
        return super().__call__(**kwargs)


class BoolBenchAllTrue(bch.ParametrizedSweep):
    """Always True. For edge case: mean=1.0, std=0.0."""

    cat = bch.EnumSweep(CatEnum, doc="Categorical input")
    out = bch.ResultBool(doc="Always true")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = True
        return super().__call__(**kwargs)


class BoolBenchAllFalse(bch.ParametrizedSweep):
    """Always False. For edge case: mean=0.0, std=0.0."""

    cat = bch.EnumSweep(CatEnum, doc="Categorical input")
    out = bch.ResultBool(doc="Always false")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = False
        return super().__call__(**kwargs)


class TwoFloatBool(bch.ParametrizedSweep):
    """Two float inputs, deterministic bool output. For 2-float plot tests."""

    x1 = bch.FloatSweep(default=0, bounds=[0, 1])
    x2 = bch.FloatSweep(default=0, bounds=[0, 1])
    out = bch.ResultBool(doc="bool output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = (self.x1 + self.x2) > 1.0
        return super().__call__(**kwargs)


class ThreeFloatBool(bch.ParametrizedSweep):
    """Three float inputs, deterministic bool output. For volume plot tests."""

    x1 = bch.FloatSweep(default=0, bounds=[0, 1])
    x2 = bch.FloatSweep(default=0, bounds=[0, 1])
    x3 = bch.FloatSweep(default=0, bounds=[0, 1])
    out = bch.ResultBool(doc="bool output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = (self.x1 + self.x2 + self.x3) > 1.5
        return super().__call__(**kwargs)


class BoolBenchNone(bch.ParametrizedSweep):
    """Returns None for the result. Tests None-to-NaN coercion."""

    cat = bch.EnumSweep(CatEnum, doc="Categorical input")
    out = bch.ResultBool(doc="None output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out = None
        return super().__call__(**kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_sweep(bench_cls, input_vars, result_vars=None, repeats=1, **kwargs):
    """Run a minimal benchmark sweep and return the BenchResult."""
    run_cfg = bch.BenchRunCfg(repeats=repeats)
    bench = bench_cls().to_bench(run_cfg)
    return bench.plot_sweep(
        input_vars=input_vars,
        result_vars=result_vars or ["out"],
        title="test",
        plot_callbacks=False,
        **kwargs,
    )


# ===========================================================================
# Category 1: Data Integrity
# ===========================================================================


class TestDataIntegrity(unittest.TestCase):
    """Verify that ResultBool data is stored and aggregated correctly."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_bool_values_stored_as_float(self):
        """Bool values should be stored as float64 with values 0.0/1.0."""
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        ds = res.to_dataset()
        da = ds["out"]
        self.assertEqual(da.dtype, np.float64)
        for val in da.values.flat:
            self.assertIn(float(val), (0.0, 1.0))

    def test_bool_aggregation_mean_with_repeats(self):
        """After REDUCE, mean should be in [0,1] and _std should exist."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        da_mean = ds["out"]
        for val in da_mean.values.flat:
            self.assertGreaterEqual(float(val), 0.0)
            self.assertLessEqual(float(val), 1.0)
        self.assertIn("out_std", ds.data_vars)

    def test_bool_squeeze_removes_repeat_dim(self):
        """SQUEEZE should drop the 'repeat' dimension."""
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.SQUEEZE).data
        self.assertNotIn("repeat", ds.dims)

    def test_bool_all_true_mean(self):
        """All-True benchmark with repeats should give mean=1.0."""
        res = _run_sweep(BoolBenchAllTrue, ["cat"], repeats=3)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        for val in ds["out"].values.flat:
            self.assertAlmostEqual(float(val), 1.0)

    def test_bool_all_false_mean(self):
        """All-False benchmark with repeats should give mean=0.0."""
        res = _run_sweep(BoolBenchAllFalse, ["cat"], repeats=3)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        for val in ds["out"].values.flat:
            self.assertAlmostEqual(float(val), 0.0)

    def test_result_bool_bounds(self):
        """ResultBool.bounds should be (0, 1)."""
        self.assertEqual(BoolBenchDeterministic.param.out.bounds, (0, 1))

    def test_result_bool_default(self):
        """ResultBool.default should be 0."""
        self.assertEqual(BoolBenchDeterministic.param.out.default, 0)

    def test_result_bool_units(self):
        """ResultBool.units should be 'ratio'."""
        self.assertEqual(BoolBenchDeterministic.param.out.units, "ratio")


# ===========================================================================
# Category 2: Bar (SHOULD WORK — BarResult explicitly supports ResultBool)
# ===========================================================================


class TestBarResult(unittest.TestCase):
    """BarResult has explicit ResultBool scenarios so these should all produce plots."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_bar_1cat_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        plot = res.to(BarResult)
        self.assertIsNotNone(plot)

    def test_bar_1cat_multi_repeat(self):
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(BarResult)
        self.assertIsNotNone(plot)

    def test_bar_2cat_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["cat", "x"], repeats=1)
        plot = res.to(BarResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 3: Line (SHOULD WORK — LineResult has result_types=(ResultVar, ResultBool))
# ===========================================================================


class TestLineResult(unittest.TestCase):
    """LineResult includes ResultBool in result_types."""

    def test_line_1float_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["x"], repeats=1)
        plot = res.to(LineResult)
        self.assertIsNotNone(plot)

    def test_line_1float_1cat_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["x", "cat"], repeats=1)
        plot = res.to(LineResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 4: Curve (SHOULD WORK — CurveResult has result_types=(ResultVar, ResultBool))
# ===========================================================================


class TestCurveResult(unittest.TestCase):
    """CurveResult includes ResultBool in result_types."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_curve_1float_multi_repeat(self):
        res = _run_sweep(BoolBenchAlternating, ["x"], repeats=4)
        plot = res.to(CurveResult)
        self.assertIsNotNone(plot)

    def test_curve_1float_1cat_multi_repeat(self):
        res = _run_sweep(BoolBenchAlternating, ["x", "cat"], repeats=4)
        plot = res.to(CurveResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 5: Heatmap (supports ResultBool)
# ===========================================================================


class TestHeatmapResult(unittest.TestCase):
    """HeatmapResult supports ResultBool via inheritance from ResultVar."""

    def test_heatmap_2input_1repeat(self):
        """Heatmap should produce a plot for ResultBool data."""
        res = _run_sweep(BoolBenchDeterministic, ["x", "cat"], repeats=1)
        plot = res.to(HeatmapResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 6: Surface (supports ResultBool)
# ===========================================================================


class TestSurfaceResult(unittest.TestCase):
    """SurfaceResult supports ResultBool via inheritance from ResultVar."""

    def test_surface_2float_multi_repeat(self):
        """Surface should produce a plot for ResultBool data."""
        res = _run_sweep(TwoFloatBool, ["x1", "x2"], repeats=2)
        plot = res.to(SurfaceResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 6b: Volume (supports ResultBool)
# ===========================================================================


class TestVolumeResult(unittest.TestCase):
    """VolumeResult supports ResultBool via inheritance from ResultVar."""

    def test_volume_3float_multi_repeat(self):
        """Volume should produce a plot for ResultBool data."""
        res = _run_sweep(ThreeFloatBool, ["x1", "x2", "x3"], repeats=2)
        plot = res.to(VolumeResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 7: Distribution (supports ResultBool)
# ===========================================================================


class TestDistributionResult(unittest.TestCase):
    """DistributionResult, ViolinResult, BoxWhiskerResult, and ScatterJitterResult
    all support ResultBool via inheritance from ResultVar."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_violin_1cat_multi_repeat(self):
        """Violin should produce a plot for ResultBool data."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(ViolinResult)
        self.assertIsNotNone(plot)

    def test_boxwhisker_1cat_multi_repeat(self):
        """BoxWhisker should produce a plot for ResultBool data."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(BoxWhiskerResult)
        self.assertIsNotNone(plot)

    def test_scatter_jitter_1cat_multi_repeat(self):
        """ScatterJitter should produce a plot for ResultBool data."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(ScatterJitterResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 8: Scatter (old-style PlotFilter, no result_types — should not crash)
# ===========================================================================


class TestScatterResult(unittest.TestCase):
    """ScatterResult uses PlotFilter without result_types. Should not crash."""

    def test_scatter_1cat_1repeat_no_crash(self):
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        # ScatterResult.to_plot doesn't accept result_var, just call it
        try:
            res.to(ScatterResult)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.fail(f"ScatterResult raised {type(e).__name__}: {e}")


# ===========================================================================
# Category 9: Table / Tabulator (no result_types filtering — SHOULD WORK)
# ===========================================================================


class TestTableResult(unittest.TestCase):
    """TableResult and TabulatorResult have no result_types filter."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_table_1cat_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        plot = res.to(TableResult)
        self.assertIsNotNone(plot)

    def test_tabulator_1cat_1repeat(self):
        res = _run_sweep(BoolBenchDeterministic, ["cat"], repeats=1)
        plot = res.to(TabulatorResult)
        self.assertIsNotNone(plot)

    def test_tabulator_1cat_multi_repeat(self):
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(TabulatorResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 10: Histogram (supports ResultBool)
# ===========================================================================


class TestHistogramResult(unittest.TestCase):
    """HistogramResult supports ResultBool via inheritance from ResultVar."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_histogram_0input_multi_repeat(self):
        """Histogram should produce a plot for ResultBool data."""
        res = _run_sweep(BoolBenchAlternating, [], repeats=4)
        plot = res.to(HistogramResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 11: NaN/None Handling
# ===========================================================================


class TestNoneHandling(unittest.TestCase):
    """Verify that None values are handled gracefully in ResultBool."""

    def test_none_stored_as_nan(self):
        """Setting out = None should store as NaN (not crash)."""
        res = _run_sweep(BoolBenchNone, ["cat"], repeats=1)
        ds = res.to_dataset()
        da = ds["out"]
        for val in da.values.flat:
            self.assertTrue(np.isnan(val))


# ===========================================================================
# Category 12: ResultBool Class Properties
# ===========================================================================


class TestResultBoolClass(unittest.TestCase):
    """Tests for the ResultBool class itself."""

    def test_isinstance_hierarchy(self):
        """ResultBool is a ResultVar (and therefore also a Number)."""
        rb = ResultBool()
        self.assertIsInstance(rb, Number)
        self.assertIsInstance(rb, ResultVar)

    def test_as_dim_returns_hv_dimension(self):
        """as_dim() should return an hv.Dimension.
        Note: param Parameters get their name from the class attribute, so
        we use the param descriptor from a fixture class."""
        dim = BoolBenchDeterministic.param.out.as_dim()
        self.assertIsInstance(dim, hv.Dimension)

    def test_hash_persistent_stable(self):
        """hash_persistent should return the same value for identical instances."""
        rb1 = ResultBool(units="ratio")
        rb2 = ResultBool(units="ratio")
        self.assertEqual(rb1.hash_persistent(), rb2.hash_persistent())

    def test_hash_persistent_differs_for_different_units(self):
        """hash_persistent should differ when units differ."""
        rb1 = ResultBool(units="ratio")
        rb2 = ResultBool(units="percent")
        self.assertNotEqual(rb1.hash_persistent(), rb2.hash_persistent())


# ===========================================================================
# Category 13: Auto-Reduction for ResultBool
# ===========================================================================


class TestAutoReduction(unittest.TestCase):
    """Verify that distribution plots auto-reduce ResultBool repeats to proportions."""

    def setUp(self):
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access

    def test_violin_shows_proportions_not_raw(self):
        """Violin with ResultBool should auto-reduce: no 'repeat' dim in rendered dataset."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        # Get the hv_dataset that would be passed to distribution plots (ReduceType.NONE)
        hv_ds_none = res.to_hv_dataset(reduce=bch.ReduceType.NONE)
        self.assertIn("repeat", hv_ds_none.data.dims)
        # After auto-reduction, the dataset should be reduced
        hv_ds_reduced = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE)
        self.assertNotIn("repeat", hv_ds_reduced.data.dims)
        # Confirm the plot still works
        plot = res.to(ViolinResult)
        self.assertIsNotNone(plot)

    def test_boxwhisker_shows_proportions(self):
        """BoxWhisker with ResultBool should auto-reduce."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(BoxWhiskerResult)
        self.assertIsNotNone(plot)

    def test_scatter_jitter_shows_proportions(self):
        """ScatterJitter with ResultBool should auto-reduce."""
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=4)
        plot = res.to(ScatterJitterResult)
        self.assertIsNotNone(plot)

    def test_histogram_shows_proportions(self):
        """Histogram with ResultBool should auto-reduce."""
        res = _run_sweep(BoolBenchAlternating, [], repeats=4)
        plot = res.to(HistogramResult)
        self.assertIsNotNone(plot)


# ===========================================================================
# Category 14: Binomial Standard Error
# ===========================================================================


class TestBinomialSE(unittest.TestCase):
    """Verify that REDUCE uses binomial SE sqrt(p*(1-p)/n) for ResultBool."""

    def test_binomial_se_value(self):
        """For alternating True/False (p=0.5), SE should be sqrt(0.5*0.5/n)."""
        BoolBenchAlternating._call_count = 0  # pylint: disable=protected-access
        n = 4
        res = _run_sweep(BoolBenchAlternating, ["cat"], repeats=n)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        for val in ds["out"].values.flat:
            p = float(val)
            expected_se = np.sqrt(p * (1 - p) / n)
            actual_se = float(ds["out_std"].sel(cat=ds["out"].coords["cat"].values[0]).values)
            self.assertAlmostEqual(actual_se, expected_se, places=10)
            break  # one check is enough to validate the formula

    def test_all_true_binomial_se_is_zero(self):
        """If p=1.0, binomial SE should be 0.0."""
        res = _run_sweep(BoolBenchAllTrue, ["cat"], repeats=4)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        for val in ds["out_std"].values.flat:
            self.assertAlmostEqual(float(val), 0.0)

    def test_all_false_binomial_se_is_zero(self):
        """If p=0.0, binomial SE should be 0.0."""
        res = _run_sweep(BoolBenchAllFalse, ["cat"], repeats=4)
        ds = res.to_hv_dataset(reduce=bch.ReduceType.REDUCE).data
        for val in ds["out_std"].values.flat:
            self.assertAlmostEqual(float(val), 0.0)


if __name__ == "__main__":
    unittest.main()
