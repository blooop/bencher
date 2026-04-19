"""Tests for bencher.regression module."""

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
    detect_regression,
    detect_regressions,
    render_regression_png,
)
from bencher.variables.results import OptDir


# ── detect_regression ──────────────────────────────────────────────────────


class TestDetectRegression:
    """Unified detector. One step test (always), one drift test (optional),
    expressed in MAD-sigma units. Noise is estimated with layered fallbacks.
    """

    def _rng(self):
        return np.random.default_rng(0)

    # ---- false-positive suppression ----

    def test_stable_low_noise_no_regression(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 0.5, 20)
        curr = np.array([100.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_stable_high_noise_no_regression(self):
        """Noisy but stable signal must not trip a regression."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 15.0, 20)
        curr = 100.0 + rng.normal(0, 15.0, 10)
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed, f"false positive on noisy-stable signal: {result.details}"

    def test_isolated_historical_outlier_no_regression(self):
        """A single glitch in history must not move the baseline."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        hist[5] = 500.0
        curr = np.array([101.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_heavy_tailed_noise_no_regression(self):
        rng = self._rng()
        hist = 100.0 + rng.standard_t(2, size=30)
        curr = np.array([100.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_oscillating_stable_no_regression(self):
        """Periodic signal centered at baseline — MK p-value should be high."""
        i = np.arange(20, dtype=float)
        hist = 100.0 + 10.0 * np.sin(i)
        curr = np.array([101.0])
        result = detect_regression(
            "x", hist, curr, direction=OptDir.minimize, historical_time_means=hist
        )
        assert not result.regressed

    # ---- true-positive detection ----

    def test_sudden_regression_on_noisy_signal(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 15.0, 20)
        curr = 150.0 + rng.normal(0, 15.0, 10)
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert result.regressed
        assert "step" in result.details

    def test_gradual_drift_on_noisy_signal(self):
        rng = self._rng()
        i = np.arange(20, dtype=float)
        hist = 100.0 + 1.5 * i + rng.normal(0, 5.0, 20)
        curr = np.array([float(100.0 + 1.5 * 20)])
        result = detect_regression(
            "x", hist, curr, direction=OptDir.minimize, historical_time_means=hist
        )
        assert result.regressed
        assert "drift" in result.details

    def test_improvement_not_regression_minimize(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([50.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_improvement_not_regression_maximize(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([150.0])
        result = detect_regression("x", hist, curr, direction=OptDir.maximize)
        assert not result.regressed

    def test_direction_none_fires_either_way(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([150.0])
        result = detect_regression("x", hist, curr, direction=OptDir.none)
        assert result.regressed

    # ---- sparse / edge-case history (layered noise fallback) ----

    def test_sparse_history_still_runs(self):
        """Short history must still produce a verdict via the relative floor."""
        hist = np.array([100.0, 101.0, 99.0])
        curr = np.array([100.0, 102.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert result.method == "regression"
        assert np.isfinite(result.baseline_value)

    def test_single_historical_sample_runs(self):
        """Even a single prior sample produces a result."""
        hist = np.array([100.0])
        curr = np.array([100.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_constant_history_with_identical_current(self):
        """Zero-variance history with matching current must not fire."""
        hist = np.full(20, 100.0)
        curr = np.array([100.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    def test_nan_current_is_guarded(self):
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 1.0, 20)
        curr = np.array([np.nan, np.nan])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert not result.regressed

    # ---- integer / stable metric (min_change_percent guard) ----

    def test_integer_metric_one_step_fires_without_guard(self):
        """Default behaviour: stable integer + one-unit change fires on z-score.

        This is the documented pathology — the user opts out of it by setting
        min_change_percent. Locked in as a regression test so the behaviour is
        explicit.
        """
        hist = np.full(20, 100.0, dtype=float)
        curr = np.array([101.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert result.regressed

    def test_integer_metric_one_step_suppressed_by_guard(self):
        """With min_change_percent=5, a 1% change on a stable baseline is ignored."""
        hist = np.full(20, 100.0, dtype=float)
        curr = np.array([101.0])
        result = detect_regression(
            "x", hist, curr, direction=OptDir.minimize, min_change_percent=5.0
        )
        assert not result.regressed

    def test_min_change_percent_still_fires_on_big_change(self):
        """Guard doesn't suppress legitimate regressions."""
        hist = np.full(20, 100.0, dtype=float)
        curr = np.array([200.0])
        result = detect_regression(
            "x", hist, curr, direction=OptDir.minimize, min_change_percent=5.0
        )
        assert result.regressed

    def test_noise_floor_reports_source(self):
        """The `details` string identifies which noise-estimation layer fired."""
        rng = self._rng()
        hist = 100.0 + rng.normal(0, 2.0, 20)
        curr = np.array([100.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert "(mad)" in result.details

    def test_noise_floor_residual_on_strict_monotone(self):
        """Pure linear history has MAD that correlates with trend, so MAD > 0
        still triggers the 'mad' branch. This test just verifies noise is finite."""
        hist = np.arange(20, dtype=float) + 100.0
        curr = np.array([120.0])
        result = detect_regression("x", hist, curr, direction=OptDir.minimize)
        assert np.isfinite(result.band_lower)
        assert np.isfinite(result.band_upper)


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
                    method="regression",
                    regressed=True,
                    current_value=110.0,
                    baseline_value=100.0,
                    change_percent=10.0,
                    threshold=3.5,
                    direction="minimize",
                    details="test",
                ),
                RegressionResult(
                    variable="metric_b",
                    method="regression",
                    regressed=False,
                    current_value=101.0,
                    baseline_value=100.0,
                    change_percent=1.0,
                    threshold=3.5,
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
    def _make_cfg(result_vars, threshold=None, min_change_percent=None):
        class FakeBenchCfg:
            def __init__(self, result_vars):
                self.result_vars = result_vars

        class FakeRunCfg:
            def __init__(self, threshold, min_change_percent):
                self.regression_threshold = threshold
                self.regression_min_change_percent = min_change_percent

        return FakeBenchCfg(result_vars), FakeRunCfg(threshold, min_change_percent)

    def test_no_over_time_dim(self):
        ds = xr.Dataset({"x": (["repeat"], [1.0, 2.0])})

        class FakeCfg:
            result_vars = []

        class FakeRun:
            regression_threshold = None
            regression_min_change_percent = None

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

    def test_detects_big_step(self):
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
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert report.results[0].variable == "metric"
        assert report.results[0].change_percent > 50

    def test_no_false_positive_on_noisy_stable(self):
        rng = np.random.default_rng(0)
        values = 100.0 + rng.normal(0, 15.0, size=(20, 4))
        ds = self._make_dataset(n_times=20, n_repeats=4, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert not report.has_regressions, report.summary()

    def test_detects_sudden_step_via_adaptive(self):
        rng = np.random.default_rng(0)
        stable = 100.0 + rng.normal(0, 2.0, size=(20, 4))
        jump = 150.0 + rng.normal(0, 2.0, size=(1, 4))
        values = np.vstack([stable, jump])
        ds = self._make_dataset(n_times=21, n_repeats=4, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert report.has_regressions
        assert "step" in report.results[0].details

    def test_detects_gradual_drift(self):
        rng = np.random.default_rng(0)
        n_times = 20
        n_repeats = 4
        base = np.arange(n_times, dtype=float)[:, None] * 1.5 + 100.0
        values = base + rng.normal(0, 3.0, size=(n_times, n_repeats))
        ds = self._make_dataset(n_times=n_times, n_repeats=n_repeats, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5)
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
        """Two result vars, one stable, one step — only the step fires."""
        rng = np.random.default_rng(0)
        # metric_a: clearly degraded at the last point
        a_stable = 100.0 + rng.normal(0, 2.0, size=(10, 4))
        a_jump = 200.0 + rng.normal(0, 2.0, size=(1, 4))
        values_a = np.vstack([a_stable, a_jump])
        # metric_b: oscillating around a fixed baseline so no drift trend
        ncoord = values_a.shape[0]
        nrep = values_a.shape[1]
        i = np.arange(ncoord, dtype=float)[:, None]
        values_b = 50.0 + 0.5 * np.sin(i) + np.zeros((1, nrep))
        ds = xr.Dataset(
            {
                "metric_a": (["over_time", "repeat"], values_a),
                "metric_b": (["over_time", "repeat"], values_b),
            },
            coords={"over_time": np.arange(ncoord), "repeat": np.arange(nrep)},
        )
        from bencher.variables.results import ResultFloat

        rv_a = ResultFloat(units="s", direction=OptDir.minimize)
        rv_a.name = "metric_a"
        rv_b = ResultFloat(units="s", direction=OptDir.minimize)
        rv_b.name = "metric_b"
        bench_cfg, run_cfg = self._make_cfg([rv_a, rv_b], threshold=3.5)
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 2
        assert report.has_regressions
        names = {r.variable: r.regressed for r in report.results}
        assert names["metric_a"] is True
        assert names["metric_b"] is False

    def test_var_not_in_dataset_skipped(self):
        values = np.array([[100.0, 100.0], [200.0, 200.0]])
        ds = self._make_dataset(n_times=2, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "nonexistent"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 0

    def test_non_numeric_result_var_skipped(self):
        values = np.array([[100.0, 100.0], [200.0, 200.0]])
        ds = self._make_dataset(n_times=2, n_repeats=2, values=values)
        from bencher.variables.results import ResultImage

        rv = ResultImage(doc="test image")
        rv.name = "metric"
        bench_cfg, run_cfg = self._make_cfg([rv])
        report = detect_regressions(ds, bench_cfg, run_cfg)
        assert len(report.results) == 0

    def test_custom_threshold_overrides_default(self):
        """Explicit threshold changes sensitivity."""
        rng = np.random.default_rng(0)
        stable = 100.0 + rng.normal(0, 2.0, size=(5, 2))
        jump = 110.0 + rng.normal(0, 2.0, size=(1, 2))
        values = np.vstack([stable, jump])
        ds = self._make_dataset(n_times=6, n_repeats=2, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"

        bench_cfg_strict, run_cfg_strict = self._make_cfg([rv], threshold=2.0)
        report_strict = detect_regressions(ds, bench_cfg_strict, run_cfg_strict)
        assert report_strict.has_regressions

        bench_cfg_loose, run_cfg_loose = self._make_cfg([rv], threshold=10.0)
        report_loose = detect_regressions(ds, bench_cfg_loose, run_cfg_loose)
        assert not report_loose.has_regressions

    def test_min_change_percent_applied_via_cfg(self):
        """run_cfg.regression_min_change_percent reaches the detector."""
        # Stable integer series, single-unit jump
        values = np.full((10, 1), 100.0)
        values[-1, 0] = 101.0
        ds = self._make_dataset(n_times=10, n_repeats=1, values=values)
        from bencher.variables.results import ResultFloat

        rv = ResultFloat(units="s", direction=OptDir.minimize)
        rv.name = "metric"

        # Without guard — fires on integer pathology
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5)
        assert detect_regressions(ds, bench_cfg, run_cfg).has_regressions

        # With guard — suppressed
        bench_cfg, run_cfg = self._make_cfg([rv], threshold=3.5, min_change_percent=5.0)
        assert not detect_regressions(ds, bench_cfg, run_cfg).has_regressions

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
        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 2
        run_cfg.regression_detection = True
        run_cfg.regression_fail = False
        run_cfg.auto_plot = False
        run_cfg.headless = True
        run_cfg.clear_cache = True
        run_cfg.clear_history = True

        bench = bn.Bench("test_regression_e2e", _SimpleBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None
        run_cfg.clear_history = False
        res2 = bench.plot_sweep(plot_callbacks=False)

        assert res2.regression_report is not None
        assert not res2.regression_report.has_regressions

    def test_detection_disabled_leaves_report_none(self):
        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 1
        run_cfg.regression_detection = False
        run_cfg.auto_plot = False
        run_cfg.headless = True
        run_cfg.clear_cache = True
        run_cfg.clear_history = True

        bench = bn.Bench("test_regression_disabled", _SimpleBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None
        run_cfg.clear_history = False
        res2 = bench.plot_sweep(plot_callbacks=False)

        assert res2.regression_report is None

    def test_regression_fail_raises(self):
        _degrade_state["counter"] = 0

        run_cfg = bn.BenchRunCfg()
        run_cfg.over_time = True
        run_cfg.repeats = 1
        run_cfg.regression_detection = True
        run_cfg.regression_fail = True
        run_cfg.auto_plot = False
        run_cfg.headless = True
        run_cfg.clear_cache = True
        run_cfg.clear_history = True

        bench = bn.Bench("test_regression_fail", _DegradingBench(), run_cfg=run_cfg)
        bench.plot_sweep(plot_callbacks=False)
        bench.sample_cache = None

        run_cfg.clear_history = False
        with pytest.raises(bn.RegressionError):
            bench.plot_sweep(plot_callbacks=False)


# ── Renderers ───────────────────────────────────────────────────────────────


def _make_result(historical_x=None, current_x=None):
    hist = np.array([100.0, 102.0, 99.0, 101.0, 100.5, 98.5, 101.2])
    curr = np.array([130.0])
    r = detect_regression("metric", hist, curr, direction=OptDir.minimize)
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
        r = _make_result()
        out = tmp_path / "alias.png"
        r.render_png(path=str(out))
        assert out.exists()


class TestBuildRegressionOverlay:
    """build_regression_overlay should render through bokeh on every x dtype."""

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
        labels = [f"2024-06-{15 + i:02d} abc{i}234d" for i in range(7)]
        r = _make_result(historical_x=labels, current_x="2024-06-22 xyz7890")
        self._render_through_panel(build_regression_overlay(r), tmp_path, "git")

    def test_overlay_band_present(self):
        import holoviews as hv

        labels = [f"2024-06-{15 + i:02d} abc{i}234d" for i in range(7)]
        r = _make_result(historical_x=labels, current_x="2024-06-22 xyz7890")
        overlay = build_regression_overlay(r)
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
    _ctr[0] += 1
    return f"2026-{_ctr[0]:02d}-01 fake{_ctr[0]:04x}"


def _duplicate_fake_time_src() -> str:
    return "2026-01-01 samecommit"


class TestOverTimeStringCoords:
    """End-to-end tests against bencher's plot pipeline with git_time_event-
    style string over_time coords."""

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
        _ctr[0] = 0
        bench = self._build_bench([_unique_fake_time_src() for _ in range(3)])
        res = bench.results[-1]
        panel = res.to_auto_plots()
        assert panel is not None

    def test_to_auto_plots_duplicate_string_times(self):
        bench = self._build_bench([_duplicate_fake_time_src() for _ in range(3)])
        res = bench.results[-1]
        panel = res.to_auto_plots()
        assert panel is not None

    def test_regression_report_populated_with_string_times(self):
        _ctr[0] = 0
        bench = self._build_bench([_unique_fake_time_src() for _ in range(4)])
        res = bench.results[-1]
        assert res.regression_report is not None
        assert res.regression_report.results, "expected at least one result"
        r = res.regression_report.results[0]
        assert r.historical_x is not None
        assert r.historical_x.dtype.kind == "U"
        import panel as pn

        overlay = r.render_overlay()
        pn.Column(pn.pane.HoloViews(overlay))
