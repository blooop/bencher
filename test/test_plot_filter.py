import unittest

from hypothesis import given
from hypothesis import strategies as st

from bencher.plotting.plot_filter import PlotFilter, PltCntCfg, VarRange


class TestVarRange(unittest.TestCase):
    def test_matches_zero(self) -> None:
        zero_case = VarRange.exactly(0)
        self.assertTrue(zero_case.matches(0))
        self.assertFalse(zero_case.matches(1))

    def test_matches_upto(self) -> None:
        var_range = VarRange.at_most(1)
        # self.assertFalse(zero_case.matches(-1))
        self.assertTrue(var_range.matches(0))
        self.assertTrue(var_range.matches(1))
        self.assertFalse(var_range.matches(2))

    @given(st.integers())
    def test_none_matches_nothing(self, val) -> None:
        """VarRange.none() must reject every count (and still reject negatives)."""
        var_range = VarRange.none()
        if val >= 0:
            self.assertFalse(var_range.matches(val))
        else:
            with self.assertRaises(ValueError):
                var_range.matches(val)

    @given(st.integers(min_value=0))
    def test_unbounded_matches_everything(self, val) -> None:
        """VarRange.unbounded() must accept every count."""
        self.assertTrue(VarRange.unbounded().matches(val))

    @given(st.integers(min_value=0))
    def test_at_least_has_no_upper_bound(self, val) -> None:
        """at_least(2) accepts 2 and every larger count, and nothing below it."""
        var_range = VarRange.at_least(2)
        self.assertEqual(var_range.matches(val), val >= 2)

    def test_exactly(self) -> None:
        var_range = VarRange.exactly(2)
        self.assertFalse(var_range.matches(1))
        self.assertTrue(var_range.matches(2))
        self.assertFalse(var_range.matches(3))

    def test_between(self) -> None:
        var_range = VarRange.between(1, 3)
        self.assertFalse(var_range.matches(0))
        for val in (1, 2, 3):
            self.assertTrue(var_range.matches(val))
        self.assertFalse(var_range.matches(4))

    def test_ranges_are_frozen_and_comparable(self) -> None:
        """Frozen + value equality is what lets the ranges be shared as defaults."""
        self.assertEqual(VarRange.unbounded(), VarRange.at_least(0))
        self.assertEqual(VarRange.exactly(2), VarRange.between(2, 2))
        self.assertNotEqual(VarRange.none(), VarRange.exactly(0))
        self.assertEqual(hash(VarRange.exactly(1)), hash(VarRange.exactly(1)))

    def test_nonsense_bounds_are_rejected(self) -> None:
        """The old two-sentinel constructor could express these; the new one cannot."""
        with self.assertRaises(ValueError):
            VarRange.between(2, 1)
        with self.assertRaises(ValueError):
            VarRange.at_least(-1)
        with self.assertRaises(ValueError):
            VarRange.exactly(-1)

    def test_str_round_trips_to_its_constructor(self) -> None:
        for var_range, text in (
            (VarRange.none(), "VarRange.none()"),
            (VarRange.exactly(2), "VarRange.exactly(2)"),
            (VarRange.at_most(2), "VarRange.at_most(2)"),
            (VarRange.between(1, 3), "VarRange.between(1, 3)"),
            (VarRange.at_least(2), "VarRange.at_least(2)"),
            (VarRange.unbounded(), "VarRange.unbounded()"),
        ):
            self.assertEqual(str(var_range), text)


class TestPlotFilter(unittest.TestCase):
    @given(st.integers(min_value=0), st.integers(min_value=0))
    def test_default_filter_matches_everything(self, float_cnt, cat_cnt) -> None:
        """Every PlotFilter field defaults to VarRange.unbounded(), so an omitted
        field never narrows the filter. A default PlotFilter() matches any shape."""

        self.assertTrue(
            PlotFilter()
            .matches_result(
                PltCntCfg(float_cnt=float_cnt, cat_cnt=cat_cnt),
                "test_default_filter_matches_everything",
                False,
            )
            .overall
        )

    def test_omitted_fields_do_not_narrow(self) -> None:
        """Stating one dimension must not silently constrain the other four."""
        cfg = PltCntCfg(float_cnt=1, cat_cnt=3, panel_cnt=2, repeats=4, inputs_cnt=4)
        pf = PlotFilter(float_range=VarRange.exactly(1))
        self.assertTrue(pf.matches_result(cfg, "one_float_only", False).overall)

    def test_matches_float(self) -> None:
        # match only float from 0 to 1
        pf = PlotFilter(
            float_range=VarRange.at_most(1),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.unbounded(),
            input_range=VarRange.unbounded(),
        )

        self.assertTrue(
            pf.matches_result(PltCntCfg(float_cnt=0), "test_matches_float0", False).overall
        )
        self.assertTrue(
            pf.matches_result(PltCntCfg(float_cnt=1), "test_matches_float1", False).overall
        )
        self.assertFalse(
            pf.matches_result(PltCntCfg(float_cnt=2), "test_matches_float2", False).overall
        )

    @given(st.integers(min_value=0))
    def test_matches_float_cat(self, cat_cnt) -> None:
        # match any cat count but only float from 0 to 1
        pf = PlotFilter(
            float_range=VarRange.at_most(1),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.unbounded(),
            input_range=VarRange.unbounded(),
        )

        self.assertTrue(
            pf.matches_result(
                PltCntCfg(float_cnt=0, cat_cnt=cat_cnt), "test_matches_float0_cat", False
            ).overall
        )
        self.assertTrue(
            pf.matches_result(
                PltCntCfg(float_cnt=1, cat_cnt=cat_cnt), "test_matches_float1_cat", False
            ).overall
        )
        self.assertFalse(
            pf.matches_result(
                PltCntCfg(float_cnt=2, cat_cnt=cat_cnt), "test_matches_float2_cat", False
            ).overall
        )
