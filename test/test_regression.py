"""Tests for bencher.regression module."""

import numpy as np
import pytest
import xarray as xr

import bencher as bch
from bencher.regression import (
    RegressionError,
    RegressionReport,
    RegressionResult,
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
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert not result.regressed

    def test_regression_above_threshold_minimize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([110.0, 112.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert result.regressed
        assert result.change_percent > 5.0

    def test_regression_below_threshold_maximize(self):
        hist = np.array([100.0, 100.0, 100.0])
        curr = np.array([90.0, 88.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.maximize)
        assert result.regressed
        assert result.change_percent < -5.0

    def test_improvement_not_regression_minimize(self):
        """For minimize, a decrease is an improvement, not a regression."""
        hist = np.array([100.0, 100.0])
        curr = np.array([80.0, 82.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert not result.regressed

    def test_improvement_not_regression_maximize(self):
        """For maximize, an increase is an improvement, not a regression."""
        hist = np.array([100.0, 100.0])
        curr = np.array([120.0, 118.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.maximize)
        assert not result.regressed

    def test_direction_none_any_change(self):
        hist = np.array([100.0, 100.0])
        curr = np.array([110.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.none)
        assert result.regressed

    def test_zero_baseline(self):
        hist = np.array([0.0, 0.0])
        curr = np.array([1.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert result.regressed
        assert result.change_percent == float("inf")

    def test_zero_baseline_zero_current(self):
        hist = np.array([0.0, 0.0])
        curr = np.array([0.0])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert not result.regressed
        assert result.change_percent == 0.0

    def test_nan_handling(self):
        hist = np.array([100.0, np.nan, 100.0])
        curr = np.array([100.0, np.nan])
        result = detect_percentage(hist, curr, threshold_percent=5.0, direction=OptDir.minimize)
        assert not result.regressed


# ── detect_iqr ─────────────────────────────────────────────────────────────


class TestDetectIqr:
    def test_within_bounds(self):
        time_means = np.array([100.0, 101.0, 99.0, 100.5, 98.5])
        curr = np.array([101.0])
        result = detect_iqr(time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert not result.regressed

    def test_outlier_above_minimize(self):
        time_means = np.array([10.0, 10.1, 10.2, 10.0, 9.9])
        curr = np.array([20.0])
        result = detect_iqr(time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert result.regressed

    def test_outlier_below_maximize(self):
        time_means = np.array([10.0, 10.1, 10.2, 10.0, 9.9])
        curr = np.array([1.0])
        result = detect_iqr(time_means, curr, iqr_scale=1.5, direction=OptDir.maximize)
        assert result.regressed

    def test_fallback_with_few_points(self):
        """With <4 historical time points, should fall back to percentage."""
        time_means = np.array([100.0, 101.0])
        curr = np.array([200.0])
        result = detect_iqr(time_means, curr, iqr_scale=1.5, direction=OptDir.minimize)
        assert result.method == "percentage"  # fell back
        assert result.regressed


# ── detect_ttest ───────────────────────────────────────────────────────────


class TestDetectTtest:
    def test_no_significant_difference(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(100, 1, 30)
        result = detect_ttest(hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert not result.regressed

    def test_significant_increase_minimize(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(110, 1, 30)
        result = detect_ttest(hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert result.regressed

    def test_significant_decrease_maximize(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(90, 1, 30)
        result = detect_ttest(hist, curr, alpha=0.05, direction=OptDir.maximize)
        assert result.regressed

    def test_fallback_single_sample(self):
        hist = np.array([100.0])
        curr = np.array([200.0])
        result = detect_ttest(hist, curr, alpha=0.05, direction=OptDir.minimize)
        assert result.method == "percentage"  # fell back

    def test_direction_none_two_sided(self):
        rng = np.random.RandomState(42)
        hist = rng.normal(100, 1, 30)
        curr = rng.normal(110, 1, 30)
        result = detect_ttest(hist, curr, alpha=0.05, direction=OptDir.none)
        assert result.regressed


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
            pass

        class FakeRunCfg:
            pass

        bench_cfg = FakeBenchCfg()
        bench_cfg.result_vars = result_vars

        run_cfg = FakeRunCfg()
        run_cfg.regression_method = method
        run_cfg.regression_threshold = threshold

        return bench_cfg, run_cfg

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
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
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
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
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
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
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
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
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
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], method="ttest", threshold=0.05)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions

    def test_all_nan(self):
        values = np.full((3, 2), np.nan)
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultVar

        rv = ResultVar(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions

    def test_result_bool_supported(self):
        values = np.array(
            [
                [0.0, 0.0],
                [0.0, 0.0],
                [1.0, 1.0],
            ]
        )
        ds = self._make_dataset(n_times=3, n_repeats=2, values=values)
        from bencher.variables.results import ResultBool

        rv = ResultBool(units="ratio", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 1


# ── RegressionError ────────────────────────────────────────────────────────


class TestRegressionError:
    def test_can_raise(self):
        with pytest.raises(RegressionError, match="test"):
            raise RegressionError("test")


# ── End-to-end with Bench ─────────────────────────────────────────────────


class _SimpleBench(bch.ParametrizedSweep):
    out_val = bch.ResultVar(units="s", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_val = 1.0
        return super().__call__(**kwargs)


_degrade_counter = 0


class _DegradingBench(bch.ParametrizedSweep):
    out_val = bch.ResultVar(units="s", direction=bch.OptDir.minimize)

    def __call__(self, **kwargs):
        global _degrade_counter
        self.update_params_from_kwargs(**kwargs)
        _degrade_counter += 1
        self.out_val = float(_degrade_counter) * 100.0
        return super().__call__(**kwargs)


class TestEndToEnd:
    def test_plot_sweep_with_regression_detection(self):
        """Full end-to-end test: run plot_sweep with over_time and regression_detection."""
        run_cfg = bch.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 2
        run_cfg.regression_detection = True
        run_cfg.regression_method = "percentage"
        run_cfg.regression_fail = False
        run_cfg.auto_plot = False
        run_cfg.headless = True

        bench = bch.Bench("test_regression_e2e", _SimpleBench(), run_cfg=run_cfg)
        # Run twice to get 2 time points with same values — no regression
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None  # reset cache for new run
        res2 = bench.plot_sweep(plot_callbacks=False)

        assert res2.regression_report is not None
        assert not res2.regression_report.has_regressions

    def test_regression_fail_raises(self):
        """Verify that regression_fail=True raises RegressionError."""
        global _degrade_counter
        _degrade_counter = 0

        run_cfg = bch.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 1
        run_cfg.regression_detection = True
        run_cfg.regression_method = "percentage"
        run_cfg.regression_fail = True
        run_cfg.auto_plot = False
        run_cfg.headless = True

        bench = bch.Bench("test_regression_fail", _DegradingBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None

        with pytest.raises(bch.RegressionError):
            bench.plot_sweep(plot_callbacks=False)
