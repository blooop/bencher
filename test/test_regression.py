"""Tests for bencher.regression module."""

import numpy as np
import pytest
import xarray as xr

import bencher as bn
from bencher.regression import (
    RegressionError,
    RegressionReport,
    RegressionResult,
    detect_adaptive,
    detect_iqr,
    detect_percentage,
    detect_regressions,
    detect_ttest,
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


# ── detect_iqr ─────────────────────────────────────────────────────────────


class TestDetectIqr:
    def test_within_bounds(self):
        time_means = np.array([100.0, 101.0, 99.0, 100.5, 98.5])
        curr = np.array([101.0])
        result = detect_iqr("x", time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert not result.regressed

    def test_outlier_above_minimize(self):
        time_means = np.array([10.0, 10.1, 10.2, 10.0, 9.9])
        curr = np.array([20.0])
        result = detect_iqr("x", time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert result.regressed

    def test_outlier_below_maximize(self):
        time_means = np.array([10.0, 10.1, 10.2, 10.0, 9.9])
        curr = np.array([1.0])
        result = detect_iqr("x", time_means, curr, iqr_scale=1.5, direction=OptDir.maximize)
        assert result.regressed

    def test_improvement_not_regression_minimize(self):
        """For minimize, an outlier below bounds is an improvement, not a regression."""
        time_means = np.array([10.0, 10.1, 10.2, 10.0, 9.9])
        curr = np.array([1.0])  # well below — improvement for minimize
        result = detect_iqr("x", time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert not result.regressed

    def test_fallback_with_few_points(self):
        """With <4 historical time points, should fall back to percentage."""
        time_means = np.array([100.0, 101.0])
        curr = np.array([200.0])
        result = detect_iqr("x", time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert result.method == "percentage"  # fell back
        assert result.regressed


# ── detect_ttest ───────────────────────────────────────────────────────────


class TestDetectTtest:
    def test_no_significant_difference(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(100, 1, 30)
        result = detect_ttest("x", hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert not result.regressed

    def test_significant_increase_minimize(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(110, 1, 30)
        result = detect_ttest("x", hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert result.regressed

    def test_significant_decrease_maximize(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(90, 1, 30)
        result = detect_ttest("x", hist, curr, alpha=0.05, direction=OptDir.maximize)
        assert result.regressed

    def test_fallback_single_sample(self):
        hist = np.array([100.0])
        curr = np.array([200.0])
        result = detect_ttest("x", hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert result.method == "percentage"  # fell back to percentage-based check
        assert result.regressed  # still correctly detected as regression
        assert result.change_percent > 0.0  # percentage change indicates degradation for minimize

    def test_direction_none_two_sided(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(110, 1, 30)
        result = detect_ttest("x", hist, curr, alpha=0.05, direction=OptDir.none)
        assert result.regressed


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
        assert result.method in ("ttest", "percentage")

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
    def _make_cfg(result_vars, method="percentage", threshold=None):
        """Create minimal bench_cfg and run_cfg mocks."""

        class FakeBenchCfg:
            def __init__(self, result_vars):
                self.result_vars = result_vars

        class FakeRunCfg:
            def __init__(self, method, threshold):
                self.regression_method = method
                self.regression_threshold = threshold

        return FakeBenchCfg(result_vars), FakeRunCfg(method, threshold)

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
        bench_cfg, run_cfg = self._make_cfg([rv], method="percentage", threshold=5.0)
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
        bench_cfg, run_cfg = self._make_cfg([rv], method="percentage", threshold=5.0)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions

    def test_iqr_method(self):
        values = np.array(
            [
                [10.0, 10.0],
                [10.0, 10.0],
                [10.0, 10.0],
                [10.0, 10.0],
                [10.0, 10.0],
                [50.0, 50.0],
            ]
        )
        ds = self._make_dataset(n_times=6, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="iqr", threshold=1.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions

    def test_ttest_method(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, (5, 10))
        curr = rng.normal(200, 1, (1, 10))
        values = np.vstack([hist, curr])
        ds = self._make_dataset(n_times=6, n_repeats=10, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="ttest", threshold=0.05)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions

    def test_adaptive_method_no_false_positive_on_noisy_stable(self):
        """Adaptive must not trip on a noisy-but-stable signal (user's pain point)."""
        rng = np.random.default_rng(0)
        values = 100.0 + rng.normal(0, 15.0, size=(20, 4))
        ds = self._make_dataset(n_times=20, n_repeats=4, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", threshold=3.5)
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
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", threshold=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert "step" in report.results[0].details

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
        bench_cfg, run_cfg = self._make_cfg([rv], method="adaptive", threshold=3.5)
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
        bench_cfg, run_cfg = self._make_cfg([rv_a, rv_b], method="percentage", threshold=5.0)
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
        bench_cfg, run_cfg = self._make_cfg([rv], method="bogus", threshold=5.0)
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

        bench_cfg_strict, run_cfg_strict = self._make_cfg([rv], method="percentage", threshold=5.0)
        report_strict = detect_regressions(ds, bench_cfg_strict, run_cfg_strict)
        assert report_strict.has_regressions

        bench_cfg_loose, run_cfg_loose = self._make_cfg([rv], method="percentage", threshold=15.0)
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
