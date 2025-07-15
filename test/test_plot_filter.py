import unittest
from bencher.plotting.plot_filter import VarRange, PlotFilter, PltCntCfg
from hypothesis import given, strategies as st


class TestVarRange(unittest.TestCase):
    def test_matches_zero(self) -> None:
        zero_case = VarRange(0, 0)
        self.assertTrue(zero_case.matches(0))
        self.assertFalse(zero_case.matches(1))

    def test_matches_upto(self) -> None:
        var_range = VarRange(0, 1)
        # self.assertFalse(zero_case.matches(-1))
        self.assertTrue(var_range.matches(0))
        self.assertTrue(var_range.matches(1))
        self.assertFalse(var_range.matches(2))

    @given(st.integers())
    def test_default_matches_nothing(self, val) -> None:
        """Check that the default constructor produces a range that always returns false (so that any matches must be defined explicitly by the developer)"""
        var_range = VarRange()
        if val >= 0:
            self.assertFalse(var_range.matches(val))
        else:
            with self.assertRaises(ValueError):
                var_range.matches(val)

    @given(st.integers(min_value=0))
    def test_matches_none_upper(self, val) -> None:
        """Check that no upper bound matches all positive integers"""
        var_range = VarRange(0, None)
        self.assertTrue(var_range.matches(val))

    @given(st.integers(min_value=0))
    def test_matches_none_none(self, val) -> None:
        """No lower and no upper bounds should always match regardless of input"""
        var_range = VarRange(None, None)
        self.assertTrue(var_range.matches(val))


class TestPlotFilter(unittest.TestCase):
    @given(st.integers(min_value=0), st.integers(min_value=0))
    def test_matches_none(self, float_cnt, cat_cnt) -> None:
        """The default plot filter should not match any inputs"""

        null_case = PlotFilter()
        self.assertFalse(
            null_case.matches_result(
                PltCntCfg(float_cnt=float_cnt, cat_cnt=cat_cnt), "test_matches_none", False
            ).overall
        )

    def test_matches_float(self) -> None:
        # match only float from 0 to 1
        pf = PlotFilter(
            float_range=VarRange(0, 1),
            cat_range=VarRange(None, None),
            repeats_range=VarRange(None, None),
            input_range=VarRange(None, None),
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
            float_range=VarRange(0, 1),
            cat_range=VarRange(None, None),
            repeats_range=VarRange(None, None),
            input_range=VarRange(None, None),
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
