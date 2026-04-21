"""Tests for bencher.regression module."""

import math
import os

import numpy as np
import pytest
import xarray as xr

import bencher as bn
from bencher.regression import (
    RegressionError,
    RegressionReport,
    RegressionResult,
    build_regression_overlay,
    detect_absolute,
    detect_adaptive,
    detect_delta,
    detect_percentage,
    detect_regressions,
    render_regression_png,
)
from bencher.variables.results import OptDir


# ── detect_percentage ──────────────────────────────────────────────────────


class TestDetectPercentage:
    def test_no_regression_within_threshold(self):
        hist = np.array([100.0, 102.0, 98.0, 101.0])
        curr = np.array([101.0, 103.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert not result.regressed

    def test_regression_above_threshold_minimize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([110.0, 112.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert result.regressed
        assert result.change_percent > 5.0

    def test_regression_below_threshold_maximize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([90.0, 88.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.maximize
        )
        assert result.regressed
        assert result.change_percent < -5.0

    def test_improvement_not_regression_minimize(self):
        """For minimize, a decrease is an improvement, not a regression."""
        hist = np.array([100.0, 100.0])
        curr = np.array([80.0, 82.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert not result.regressed

    def test_improvement_not_regression_maximize(self):
        """For maximize, an increase is an improvement, not a regression."""
        hist = np.array([100.0, 100.0])
        curr = np.array([120.0, 118.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.maximize
        )
        assert not result.regressed

    def test_direction_none_any_change(self):
        hist = np.array([100.0, 100.0])
        curr = np.array([110.0])
        result = detect_percentage("x", hist, curr, threshold_percent=5.0, direction=OptDir.none)
        assert result.regressed

    def test_zero_baseline(self):
        hist = np.array([0.0, 0.0])
        curr = np.array([1.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert result.regressed
        assert result.change_percent == float("inf")

    def test_zero_baseline_zero_current(self):
        hist = np.array([0.0, 0.0])
        curr = np.array([0.0])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert not result.regressed
        assert result.change_percent == 0.0

    def test_nan_handling(self):
        hist = np.array([100.0, np.nan, 100.0])
        curr = np.array([100.0, np.nan])
        result = detect_percentage(
            "x", hist, curr, threshold_percent=5.0, direction=OptDir.minimize
        )
        assert not result.regressed


# ── detect_adaptive ────────────────────────────────────────────────────────


class TestDetectAdaptive:
    """Noise-aware tests covering false-positive suppression and true-positive detection.

    The adaptive method estimates inherent noise via MAD and tests both sudden
    steps and long-term drift. These scenarios verify the detector stays quiet
    on stable-but-noisy signals while firing on real regressions.
    """

    def _rng(self):
        return np.random.default_rng(0)

    # ---- false-positive suppression ----

    def test_stable_low_noise_no_regression(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 0.5, 20)
        curr = np.array([100.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_stable_high_noise_no_regression(self):
        """User's case: noisy but stable signal must not trip a regression."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 15.0, 20)
        curr = 100.0 + rng.normal(0, 15.0, 10)
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed, f"false positive on noisy-stable signal: {result.details}"

    def test_isolated_historical_outlier_no_regression(self):
        """A single glitch in history must not move the baseline."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        hist[5] = 500.0  # one-off spike
        curr = np.array([101.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_heavy_tailed_noise_no_regression(self):
        """Student-t (df=2) has occasional huge draws but no drift."""
        rng = self._rng()
        hist = 100.0 + rng.standard_t(2, size=30)
        curr = np.array([100.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_oscillating_stable_no_regression(self):
        """Periodic signal centered at baseline — MK p-value should be high."""
        i = np.arange(20, dtype=float)
        hist = 100.0 + 10.0 * np.sin(i)
        curr = np.array([101.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    # ---- true-positive detection ----

    def test_sudden_regression_on_noisy_signal(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 15.0, 20)
        curr = 150.0 + rng.normal(0, 15.0, 10)
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert result.regressed
        assert "step" in result.details

    def test_gradual_drift_on_noisy_signal(self):
        rng = self._rng()
        i = np.arange(20, dtype=float)
        hist = 100.0 + 1.5 * i + rng.normal(0, 5.0, 20)
        curr = np.array([float(100.0 + 1.5 * 20)])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert result.regressed
        assert "drift" in result.details

    def test_improvement_not_regression_minimize(self):
        """For minimize, a step *down* is an improvement, not a regression."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([50.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_improvement_not_regression_maximize(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([150.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.maximize)
        assert not result.regressed

    def test_direction_none_fires_either_way(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([150.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.none)
        assert result.regressed

    # ---- fallback for sparse data ----

    def test_sparse_history_falls_back(self):
        hist = np.array([100.0, 101.0, 99.0])
        curr = np.array([100.0, 102.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert result.method == "percentage"

    def test_sparse_history_single_current_falls_back(self):
        hist = np.array([100.0, 200.0])
        curr = np.array([200.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert result.method == "percentage"

    def test_constant_history_with_identical_current(self):
        """Zero-variance history with matching current must not fire."""
        hist = np.full(20, 100.0)
        curr = np.array([100.0])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_nan_current_is_guarded(self):
        """All-NaN current must not trigger warnings or false regression."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([np.nan, np.nan])
        result = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    # ---- dual-band (regression_percentage) ----

    def test_regression_percentage_suppresses_mad_only_fire(self):
        """Tight MAD-derived noise flagged a small change; percentage gate blocks it."""
        hist = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
        # 20% change at 10 sigma — MAD would normally fire.
        curr = np.array([12.0])
        without_pct = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert without_pct.regressed
        with_pct = detect_adaptive(
            "x", hist, curr, direction=OptDir.minimize, regression_percentage=30.0
        )
        assert not with_pct.regressed
        assert with_pct.percent_band_lower is not None
        assert with_pct.percent_band_upper is not None

    def test_regression_percentage_allows_real_regression(self):
        """When both MAD and percent thresholds are exceeded, still fires."""
        hist = 100.0 + np.random.default_rng(0).normal(0, 1.0, 20)
        curr = np.array([200.0])  # 100% change and huge z
        result = detect_adaptive(
            "x", hist, curr, direction=OptDir.minimize, regression_percentage=10.0
        )
        assert result.regressed

    def test_regression_percentage_none_preserves_behavior(self):
        """Passing None is identical to leaving it unset (current behavior)."""
        rng = np.random.default_rng(0)
        hist = 100.0 + rng.normal(0, 15.0, 20)
        curr = 150.0 + rng.normal(0, 15.0, 10)
        with_none = detect_adaptive(
            "x", hist, curr, direction=OptDir.minimize, regression_percentage=None
        )
        baseline = detect_adaptive("x", hist, curr, direction=OptDir.minimize)
        assert with_none.regressed == baseline.regressed
        assert with_none.percent_band_lower is None

    def test_regression_percentage_direction_aware_improvement(self):
        """Percent gate respects optimization direction."""
        hist = np.array([10.0] * 20)
        # 20% decrease — for minimize this is improvement (never regression),
        # and the gate shouldn't change that.
        curr = np.array([8.0])
        result = detect_adaptive(
            "x", hist, curr, direction=OptDir.minimize, regression_percentage=10.0
        )
        assert not result.regressed

    def test_sparse_fallback_uses_full_samples(self):
        """Fallback must honour `historical_samples` so it sees all raw values.

        With 3 time points but many samples per point, the sparse-history
        fallback should still detect a clear regression via the percentage
        check — passing only per-time means would leave it blind to the
        per-sample variance.
        """
        rng = self._rng()
        hist_time_means = np.array([100.0, 100.0, 100.0])
        hist_samples = 100.0 + rng.normal(0, 1.0, 60)  # 3 points x 20 repeats
        curr = 110.0 + rng.normal(0, 1.0, 20)
        result = detect_adaptive(
            "x",
            hist_time_means,
            curr,
            direction=OptDir.minimize,
            historical_samples=hist_samples,
        )
        assert result.method == "percentage"
        assert result.regressed


# ── detect_delta ───────────────────────────────────────────────────────────


class TestDetectDelta:
    def test_within_tolerance_no_regression(self):
        hist = np.array([100.0, 101.0, 99.0, 100.5])
        curr = np.array([101.0, 102.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.minimize)
        assert not result.regressed
        assert result.method == "delta"

    def test_regression_above_delta_minimize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([110.0, 112.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.minimize)
        assert result.regressed
        # Band is symmetric around historical mean.
        assert result.band_lower == 95.0
        assert result.band_upper == 105.0

    def test_regression_below_delta_maximize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([90.0, 88.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.maximize)
        assert result.regressed

    def test_improvement_not_regression_minimize(self):
        hist = np.array([100.0, 100.0])
        curr = np.array([80.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.minimize)
        assert not result.regressed

    def test_improvement_not_regression_maximize(self):
        hist = np.array([100.0, 100.0])
        curr = np.array([120.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.maximize)
        assert not result.regressed

    def test_direction_none_symmetric(self):
        hist = np.array([100.0, 100.0])
        result_above = detect_delta(
            "x", hist, np.array([108.0]), max_delta=5.0, direction=OptDir.none
        )
        result_below = detect_delta(
            "x", hist, np.array([92.0]), max_delta=5.0, direction=OptDir.none
        )
        assert result_above.regressed
        assert result_below.regressed

    def test_nan_handling(self):
        hist = np.array([100.0, np.nan, 100.0])
        curr = np.array([105.0, np.nan])
        result = detect_delta("x", hist, curr, max_delta=10.0, direction=OptDir.minimize)
        assert not result.regressed

    def test_exactly_at_delta_is_not_regression(self):
        hist = np.array([100.0, 100.0])
        curr = np.array([105.0])
        result = detect_delta("x", hist, curr, max_delta=5.0, direction=OptDir.minimize)
        assert not result.regressed  # strict '>'

    def test_empty_hist_is_not_regression(self):
        """Empty history → no baseline to compare against, guard disables itself."""
        result = detect_delta(
            "x", np.array([]), np.array([105.0]), max_delta=10.0, direction=OptDir.minimize
        )
        assert not result.regressed

    def test_all_nan_hist_is_not_regression(self):
        result = detect_delta(
            "x",
            np.array([np.nan, np.nan]),
            np.array([105.0]),
            max_delta=10.0,
            direction=OptDir.minimize,
        )
        assert not result.regressed


# ── detect_absolute ────────────────────────────────────────────────────────


class TestDetectAbsolute:
    def test_under_ceiling_minimize_not_regression(self):
        result = detect_absolute("x", np.array([40.0]), limit=50.0, direction=OptDir.minimize)
        assert not result.regressed
        assert result.method == "absolute"
        assert result.baseline_value == 50.0

    def test_over_ceiling_minimize_regression(self):
        result = detect_absolute("x", np.array([60.0]), limit=50.0, direction=OptDir.minimize)
        assert result.regressed

    def test_over_floor_maximize_not_regression(self):
        result = detect_absolute("x", np.array([120.0]), limit=100.0, direction=OptDir.maximize)
        assert not result.regressed

    def test_under_floor_maximize_regression(self):
        result = detect_absolute("x", np.array([80.0]), limit=100.0, direction=OptDir.maximize)
        assert result.regressed

    def test_direction_none_not_regression(self):
        result = detect_absolute("x", np.array([1000.0]), limit=50.0, direction=OptDir.none)
        assert not result.regressed
        assert "skipped" in result.details

    def test_nan_only_current(self):
        result = detect_absolute("x", np.array([np.nan]), limit=50.0, direction=OptDir.minimize)
        # nan > 50 is False; guard should not flag.
        assert not result.regressed
        assert math.isnan(result.current_value)
        assert result.baseline_value == 50.0


# ── RegressionReport ───────────────────────────────────────────────────────


class TestRegressionReport:
    def test_empty_report(self):
        report = RegressionReport()
        assert not report.has_regressions
        assert report.regressed_variables == []
        assert "No regressions" in report.summary()

    def test_report_with_regression(self):
        report = RegressionReport(
            results=[
                RegressionResult(
                    variable="metric_a",
                    method="percentage",
                    regressed=True,
                    current_value=110.0,
                    baseline_value=100.0,
                    change_percent=10.0,
                    threshold=5.0,
                    direction="minimize",
                    details="test",
                ),
                RegressionResult(
                    variable="metric_b",
                    method="percentage",
                    regressed=False,
                    current_value=101.0,
                    baseline_value=100.0,
                    change_percent=1.0,
                    threshold=5.0,
                    direction="minimize",
                    details="test",
                ),
            ]
        )
        assert report.has_regressions
        assert len(report.regressed_variables) == 1
        assert "metric_a" in report.summary()


# ── detect_regressions integration ────────────────────────────────────────


class TestDetectRegressions:
    @staticmethod
    def _make_dataset(n_times=3, n_repeats=2, values=None):
        """Create a synthetic dataset with over_time dimension."""
        if values is None:
            values = np.arange(n_times * n_repeats, dtype=float).reshape(n_times, n_repeats)
        ds = xr.Dataset(
            {"metric": (["over_time", "repeat"], values)},
            coords={
                "over_time": np.arange(n_times),
                "repeat": np.arange(values.shape[1] if values.ndim > 1 else 1),
            },
        )
        return ds

    @staticmethod
    def _make_cfg(
        result_vars,
        method="percentage",
        regression_mad=None,
        regression_percentage=None,
        regression_delta=None,
        regression_absolute=None,
    ):
        """Create minimal bench_cfg and run_cfg mocks."""

        class FakeBenchCfg:
            def __init__(self, result_vars):
                self.result_vars = result_vars

        class FakeRunCfg:
            def __init__(
                self,
                method,
                regression_mad,
                regression_percentage,
                regression_delta,
                regression_absolute,
            ):
                self.regression_method = method
                self.regression_mad = regression_mad
                self.regression_percentage = regression_percentage
                self.regression_delta = regression_delta
                self.regression_absolute = regression_absolute

        return (
            FakeBenchCfg(result_vars),
            FakeRunCfg(
                method,
                regression_mad,
                regression_percentage,
                regression_delta,
                regression_absolute,
            ),
        )

    def test_no_over_time_dim(self):
        ds = xr.Dataset({"x": (["repeat"], [1.0, 2.0])})

        class FakeCfg:
            result_vars = []

        class FakeRun:
            regression_method = "percentage"
            regression_threshold = None

        report = detect_regressions(ds, FakeCfg(), FakeRun())
        assert not report.has_regressions

    def test_single_time_point(self):
        ds = self._make_dataset(n_times=1, values=np.array([[1.0, 2.0]]))
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions

    def test_detects_regression_percentage(self):
        # Historical: times 0-2 have mean ~100, time 3 has mean ~200
        values = np.array(
            [
                [100.0, 100.0],
                [100.0, 100.0],
                [100.0, 100.0],
                [200.0, 200.0],
            ]
        )
        ds = self._make_dataset(n_times=4, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="percentage", regression_percentage=5.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert report.results[0].variable == "metric"
        assert report.results[0].change_percent > 50

    def test_detects_no_regression(self):
        values = np.array(
            [
                [100.0, 100.0],
                [100.0, 100.0],
                [100.0, 100.0],
                [101.0, 101.0],
            ]
        )
        ds = self._make_dataset(n_times=4, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="percentage", regression_percentage=5.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions

    def test_adaptive_method_no_false_positive_on_noisy_stable(self):
        """Adaptive must not trip on a noisy-but-stable signal (user's pain point)."""
        rng = np.random.default_rng(0)
        values = 100.0 + rng.normal(0, 15.0, size=(20, 4))
        ds = self._make_dataset(n_times=20, n_repeats=4, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", regression_mad=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions, report.summary()

    def test_adaptive_method_detects_sudden_step(self):
        """Adaptive fires on a sudden jump that is large relative to noise."""
        rng = np.random.default_rng(0)
        stable = 100.0 + rng.normal(0, 2.0, size=(20, 4))
        jump = 150.0 + rng.normal(0, 2.0, size=(1, 4))
        values = np.vstack([stable, jump])
        ds = self._make_dataset(n_times=21, n_repeats=4, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", regression_mad=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert "step" in report.results[0].details

    def test_adaptive_regression_percentage_suppresses_single_repeat_fire(self):
        """Single-repeat variable with stable history + modest drop is suppressed
        when a regression percentage is set, but would otherwise fire on MAD alone."""
        # Tight history at 10 with one earlier dip; current=7 (-30%).
        values = np.array([[10.0], [10.0], [6.0], [10.0], [10.0], [7.0]])
        ds = self._make_dataset(n_times=6, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.maximize)
        rv.name = "metric"

        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", regression_mad=3.5)
        without_pct = detect_regressions(ds, bench_cfg, run_cfg)
        assert without_pct.has_regressions

        bench_cfg, run_cfg = self._make_cfg(
            [rv], method="adaptive", regression_mad=3.5, regression_percentage=40.0
        )
        with_pct = detect_regressions(ds, bench_cfg, run_cfg)
        assert not with_pct.has_regressions
        assert with_pct.results[0].percent_band_lower is not None

    def test_adaptive_method_detects_gradual_drift(self):
        """Adaptive fires on slow drift where no single step exceeds percentage."""
        rng = np.random.default_rng(0)
        n_times = 20
        n_repeats = 4
        base = np.arange(n_times, dtype=float)[:, None] * 1.5 + 100.0
        values = base + rng.normal(0, 3.0, size=(n_times, n_repeats))
        ds = self._make_dataset(n_times=n_times, n_repeats=n_repeats, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", regression_mad=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert "drift" in report.results[0].details

    def test_all_nan(self):
        values = np.full((3, 2), np.nan)
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions

    def test_multiple_result_vars_mixed(self):
        """Multiple result vars: one regressed, one not."""
        values_a = np.array([[100.0], [100.0], [200.0]])  # regresses
        values_b = np.array([[50.0], [50.0], [51.0]])  # stable
        ds = xr.Dataset(
            {
                "metric_a": (["over_time", "repeat"], values_a),
                "metric_b": (["over_time", "repeat"], values_b),
            },
            coords={"over_time": np.arange(3), "repeat": [0]},
        )
        from bencher.variables.results import ResultFloat

        rv_a = ResultFloat(units="s", direction=OptDir.minimize)
        rv_a.name = "metric_a"
        rv_b = ResultFloat(units="s", direction=OptDir.minimize)
        rv_b.name = "metric_b"
        bench_cfg, run_cfg = self._make_cfg(
            [rv_a, rv_b], method="percentage", regression_percentage=5.0
        )
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 2
        assert report.has_regressions
        names = {r.variable: r.regressed for r in report.results}
        assert names["metric_a"] is True
        assert names["metric_b"] is False

    def test_unknown_method_falls_back_to_percentage(self):
        """Unknown regression method should fall back to percentage detection."""
        values = np.array([[100.0, 100.0], [100.0, 100.0], [200.0, 200.0]])
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="bogus", regression_percentage=5.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert report.results[0].method == "percentage"

    def test_var_not_in_dataset_skipped(self):
        """Result var not present in dataset should be silently skipped."""
        values = np.array([[100.0, 100.0], [200.0, 200.0]])
        ds = self._make_dataset(n_times=2, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "nonexistent"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 0

    def test_non_numeric_result_var_skipped(self):
        """Non-numeric result types (e.g. ResultImage) should be skipped."""
        values = np.array([[100.0, 100.0], [200.0, 200.0]])
        ds = self._make_dataset(n_times=2, n_repeats=2, values=values)
        from bencher.variables.results import ResultImage

        rv = ResultImage(doc="test image")
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 0

    def test_custom_threshold_overrides_default(self):
        """Explicit threshold should override the per-method default."""
        # 10% change — regresses with threshold=5, not with threshold=15
        values = np.array([[100.0, 100.0], [100.0, 100.0], [110.0, 110.0]])
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"

        bench_cfg_strict, run_cfg_strict = self._make_cfg(
            [rv], method="percentage", regression_percentage=5.0
        )
        report_strict = detect_regressions(ds, bench_cfg_strict, run_cfg_strict)
        assert report_strict.has_regressions

        bench_cfg_loose, run_cfg_loose = self._make_cfg(
            [rv], method="percentage", regression_percentage=15.0
        )
        report_loose = detect_regressions(ds, bench_cfg_loose, run_cfg_loose)
        assert not report_loose.has_regressions

    def test_result_bool_supported(self):
        values = np.array(
            [
                [0.0, 0.0],  # baseline
                [0.0, 0.0],  # still good
                [1.0, 1.0],  # regression for direction=OptDir.minimize
            ]
        )
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultBool

        rv = ResultBool(units="ratio", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])

        report = detect_regressions(ds, bench_cfg, run_cfg)

        assert len(report.results) == 1
        assert report.has_regressions is True

        result = report.results[0]
        assert isinstance(result.regressed, bool)
        assert result.regressed is True
        assert result.method is not None

    def test_method_delta_dispatches_only_delta(self):
        """regression_method='delta' runs the delta detector alone, no percentage result."""
        values = np.array([[100.0], [100.0], [108.0]])  # +8 from baseline
        ds = self._make_dataset(n_times=3, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="delta", regression_delta=5.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 1
        assert report.results[0].method == "delta"
        assert report.results[0].regressed is True

    def test_method_absolute_dispatches_only_absolute(self):
        values = np.array([[10.0], [10.0], [12.0]])
        ds = self._make_dataset(n_times=3, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="absolute", regression_absolute=11.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 1
        assert report.results[0].method == "absolute"
        assert report.results[0].regressed is True
        assert report.results[0].baseline_value == 11.0

    def test_method_absolute_without_history(self):
        """'absolute' runs even with a single over_time point — needs no baseline."""
        values = np.array([[60.0, 70.0]])
        ds = self._make_dataset(n_times=1, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="absolute", regression_absolute=50.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 1
        assert report.results[0].method == "absolute"
        assert report.results[0].regressed is True

    def test_method_delta_missing_threshold_skipped(self, caplog):
        import logging as _logging

        values = np.array([[100.0], [100.0], [108.0]])
        ds = self._make_dataset(n_times=3, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="delta", regression_delta=None)
        with caplog.at_level(_logging.WARNING):
            report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.results == []
        assert any("regression_delta" in rec.message for rec in caplog.records)

    def test_method_absolute_opt_dir_none_skipped(self, caplog):
        import logging as _logging

        values = np.array([[10.0], [10.0], [10.0]])
        ds = self._make_dataset(n_times=3, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.none)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="absolute", regression_absolute=5.0)
        with caplog.at_level(_logging.WARNING):
            report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.results == []
        assert any("OptDir.none" in rec.message for rec in caplog.records)

    def test_method_delta_skipped_without_history(self):
        """'delta' needs a baseline — skip when n_times < 2."""
        values = np.array([[100.0]])
        ds = self._make_dataset(n_times=1, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="delta", regression_delta=1.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.results == []


# ── RegressionError ────────────────────────────────────────────────────────


class TestRegressionError:
    def test_can_raise(self):
        with pytest.raises(RegressionError, match="test"):
            raise RegressionError("test")


# ── End-to-end with Bench ─────────────────────────────────────────────────


class _SimpleBench(bn.ParametrizedSweep):
    out_val = bn.ResultFloat(units="s", direction=bn.OptDir.minimize)

    def benchmark(self):
        self.out_val = 1.0


_degrade_state = {"counter": 0}


class _DegradingBench(bn.ParametrizedSweep):
    out_val = bn.ResultFloat(units="s", direction=bn.OptDir.minimize)

    def benchmark(self):
        _degrade_state["counter"] += 1
        self.out_val = float(_degrade_state["counter"]) * 100.0


class TestEndToEnd:
    def test_plot_sweep_with_regression_detection(self):
        """Full end-to-end test: run plot_sweep with over_time and regression_detection."""
        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 2
        run_cfg.regression_detection = True
        run_cfg.regression_method = "percentage"
        run_cfg.regression_fail = False
        run_cfg.auto_plot = False
        run_cfg.headless = True

        bench = bn.Bench("test_regression_e2e", _SimpleBench(), run_cfg=run_cfg)
        # Run twice to get 2 time points with same values — no regression
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None  # reset cache for new run
        res2 = bench.plot_sweep(plot_callbacks=False)

        assert res2.regression_report is not None
        assert not res2.regression_report.has_regressions

    def test_detection_disabled_leaves_report_none(self):
        """When regression_detection=False, regression_report should stay None."""
        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 1
        run_cfg.regression_detection = False
        run_cfg.auto_plot = False
        run_cfg.headless = True

        bench = bn.Bench("test_regression_disabled", _SimpleBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None
        res2 = bench.plot_sweep(plot_callbacks=False)

        assert res2.regression_report is None

    def test_regression_fail_raises(self):
        """Verify that regression_fail=True raises RegressionError."""
        _degrade_state["counter"] = 0

        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 1
        run_cfg.regression_detection = True
        run_cfg.regression_method = "percentage"
        run_cfg.regression_fail = True
        run_cfg.auto_plot = False
        run_cfg.headless = True

        bench = bn.Bench("test_regression_fail", _DegradingBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None

        with pytest.raises(bn.RegressionError):
            bench.plot_sweep(plot_callbacks=False)


# ── Renderers ───────────────────────────────────────────────────────────────


def _make_result(historical_x=None, current_x=None):
    hist = np.array([100.0, 102.0, 99.0, 101.0, 100.5, 98.5, 101.2])
    curr = np.array([130.0])
    r = detect_percentage("metric", hist, curr, threshold_percent=5.0)
    r.historical = hist
    r.current_samples = curr
    if historical_x is not None:
        r.historical_x = np.asarray(historical_x)
    if current_x is not None:
        r.current_x = current_x
    return r


class TestRenderRegressionPng:
    """render_regression_png should handle every x-axis dtype we emit."""

    def test_png_index_axis(self, tmp_path):
        r = _make_result()
        out = tmp_path / "idx.png"
        path = render_regression_png(r, path=str(out))
        assert path == str(out)
        assert os.path.getsize(path) > 1000

    def test_png_datetime_axis(self, tmp_path):
        dates = np.array([np.datetime64("2024-01-01") + np.timedelta64(i, "D") for i in range(7)])
        r = _make_result(historical_x=dates, current_x=np.datetime64("2024-01-08"))
        out = tmp_path / "dt.png"
        path = render_regression_png(r, path=str(out))
        assert os.path.getsize(path) > 1000

    def test_png_string_axis_git_time_event(self, tmp_path):
        """git_time_event() returns strings like '2024-06-15 abc1234d'."""
        labels = [f"2024-06-{15 + i:02d} abc{i}234d" for i in range(7)]
        r = _make_result(historical_x=labels, current_x="2024-06-22 xyz7890")
        out = tmp_path / "git.png"
        path = render_regression_png(r, path=str(out))
        assert os.path.getsize(path) > 1000

    def test_png_method_alias(self, tmp_path):
        """RegressionResult.render_png delegates to the module function."""
        r = _make_result()
        out = tmp_path / "alias.png"
        r.render_png(path=str(out))
        assert out.exists()


class TestBuildRegressionOverlay:
    """build_regression_overlay should render through bokeh on every x dtype.

    The regression was: HSpan/HLine combined with a categorical x-axis threw
    UFuncNoLoopError inside holoviews' get_extents. The fix uses explicit-coord
    Area/Curve primitives, so driving it through Panel's get_root is the
    end-to-end proof that the crash is gone.
    """

    @staticmethod
    def _render_through_panel(overlay, tmp_path, name):
        import panel as pn

        col = pn.Column(pn.pane.HoloViews(overlay))
        out = tmp_path / f"{name}.html"
        col.save(str(out))
        assert out.stat().st_size > 0

    def test_overlay_index_axis(self, tmp_path):
        r = _make_result()
        self._render_through_panel(build_regression_overlay(r), tmp_path, "idx")

    def test_overlay_datetime_axis(self, tmp_path):
        dates = np.array([np.datetime64("2024-01-01") + np.timedelta64(i, "D") for i in range(7)])
        r = _make_result(historical_x=dates, current_x=np.datetime64("2024-01-08"))
        self._render_through_panel(build_regression_overlay(r), tmp_path, "dt")

    def test_overlay_string_axis_git_time_event(self, tmp_path):
        """Regression test: git_time_event strings previously crashed bokeh render."""
        labels = [f"2024-06-{15 + i:02d} abc{i}234d" for i in range(7)]
        r = _make_result(historical_x=labels, current_x="2024-06-22 xyz7890")
        self._render_through_panel(build_regression_overlay(r), tmp_path, "git")

    def test_overlay_band_present(self):
        """The acceptance band should be in the overlay (regression: bokeh
        silently dropped HSpan when combined with categorical x)."""
        import holoviews as hv

        labels = [f"2024-06-{15 + i:02d} abc{i}234d" for i in range(7)]
        r = _make_result(historical_x=labels, current_x="2024-06-22 xyz7890")
        overlay = build_regression_overlay(r)
        # The band is rendered as an Area element; assert one is present.
        has_area = any(isinstance(el, hv.Area) for el in overlay)
        assert has_area, f"expected an Area layer for the band, got: {list(overlay)}"


# ── End-to-end over_time plotting with string TimeEvent coords ─────────────

_ctr = [0]


class _StringTimeBench(bn.ParametrizedSweep):
    """Benchmark with a categorical input var — forces the bar plot path."""

    endpoint = bn.StringSweep(["a", "b", "c"], doc="endpoint")
    latency = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)
    _base = {"a": 10.0, "b": 20.0, "c": 30.0}

    def benchmark(self):
        import random

        self.latency = self._base[self.endpoint] + random.gauss(0, 1.0)


def _unique_fake_time_src() -> str:
    """git_time_event()-style string, guaranteed distinct each call."""
    _ctr[0] += 1
    return f"2026-{_ctr[0]:02d}-01 fake{_ctr[0]:04x}"


def _duplicate_fake_time_src() -> str:
    """git_time_event()-style string that repeats — simulates a user running
    multiple times within the same git commit (pre-fix crash condition)."""
    return "2026-01-01 samecommit"


class TestOverTimeStringCoords:
    """End-to-end tests against bencher's plot pipeline with git_time_event-
    style string over_time coords. Previously crashed in two places:

    - regression overlay: nanmax on Unicode dtype (fixed by categorical fallback)
    - bar plot: duplicate over_time coords → sel returns mixed element types
      → `HoloMap must only contain one type of object`.
    """

    def _build_bench(self, time_srcs):
        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.regression_detection = True
        run_cfg.auto_plot = False
        run_cfg.headless = True
        bench = bn.Bench("string_time", _StringTimeBench(), run_cfg=run_cfg)
        for i, ts in enumerate(time_srcs):
            run_cfg.clear_history = i == 0
            run_cfg.clear_cache = True
            bench.plot_sweep(
                input_vars=["endpoint"],
                result_vars=["latency"],
                run_cfg=run_cfg,
                time_src=ts,
            )
        return bench

    def test_to_auto_plots_unique_string_times(self):
        """With unique string time coords, to_auto_plots should not crash."""
        _ctr[0] = 0
        bench = self._build_bench([_unique_fake_time_src() for _ in range(3)])
        res = bench.results[-1]
        panel = res.to_auto_plots()
        assert panel is not None

    def test_to_auto_plots_duplicate_string_times(self):
        """Duplicate over_time coord values previously crashed the bar holomap
        with `HoloMap must only contain one type of object`. After the fix,
        duplicates are deduped inside _build_time_holomap via isel + seen set.
        """
        bench = self._build_bench([_duplicate_fake_time_src() for _ in range(3)])
        res = bench.results[-1]
        # Must not raise even though the dataset has duplicate over_time coords.
        panel = res.to_auto_plots()
        assert panel is not None

    def test_regression_report_populated_with_string_times(self):
        """regression_report should capture string historical_x for use by the
        PNG/overlay renderers (without crashing on dtype)."""
        _ctr[0] = 0
        bench = self._build_bench([_unique_fake_time_src() for _ in range(4)])
        res = bench.results[-1]
        assert res.regression_report is not None
        assert res.regression_report.results, "expected at least one result"
        r = res.regression_report.results[0]
        assert r.historical_x is not None
        assert r.historical_x.dtype.kind == "U"  # unicode
        # Renderers must both succeed on this result.
        import panel as pn

        overlay = r.render_overlay()
        pn.Column(pn.pane.HoloViews(overlay))  # triggers panel init render path
