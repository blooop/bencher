"""Benchmark regression detection for over-time benchmarks.

Provides statistical methods to detect if benchmark values have changed
significantly between runs. Supports percentage threshold, IQR-based outlier
detection, and Welch's t-test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from bencher.variables.results import OptDir, SCALAR_RESULT_TYPES

# Default thresholds per method — used when the user hasn't explicitly set a threshold.
_METHOD_DEFAULTS = {
    "percentage": 5.0,  # percent change
    "iqr": 1.5,  # IQR multiplier
    "ttest": 0.05,  # significance level alpha
    "adaptive": 3.5,  # robust z-score threshold in MAD units
}

# Consistency factor so MAD estimates the standard deviation of a Gaussian.
_MAD_TO_SIGMA = 1.4826

# Drift threshold defaults to this fraction of z_threshold when not set by caller.
_DRIFT_FRAC = 0.85

# Hampel filter cutoff (in MAD units) used to drop outliers from the slope fit.
_HAMPEL_K = 5.0


class RegressionError(Exception):
    """Raised when regression detection finds regressions and regression_fail is True."""


@dataclass
class RegressionResult:
    """Result of regression detection for a single variable."""

    variable: str
    method: str
    regressed: bool
    current_value: float
    baseline_value: float
    change_percent: float
    threshold: float
    direction: str
    details: str
    band_lower: float | None = None
    band_upper: float | None = None


@dataclass
class RegressionReport:
    """Aggregates regression results for all variables in a benchmark."""

    results: list[RegressionResult] = field(default_factory=list)

    @property
    def has_regressions(self) -> bool:
        return any(r.regressed for r in self.results)

    @property
    def regressed_variables(self) -> list[RegressionResult]:
        return [r for r in self.results if r.regressed]

    def summary(self) -> str:
        lines = []
        regressed = self.regressed_variables
        if not regressed:
            lines.append("No regressions detected.")
        else:
            lines.append(f"Regressions detected in {len(regressed)} variable(s):")
            for r in regressed:
                lines.append(
                    f"  {r.variable}: {r.change_percent:+.2f}% change "
                    f"(baseline={r.baseline_value:.4g}, current={r.current_value:.4g}, "
                    f"method={r.method}, threshold={r.threshold})"
                )
        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Return a nicely formatted Markdown summary of all regression results."""
        regressed = self.regressed_variables
        passed = [r for r in self.results if not r.regressed]

        lines: list[str] = []
        if regressed:
            lines.append(f"**{len(regressed)} regression(s) detected**\n")
            lines.append("| Variable | Change | Baseline | Current | Method | Threshold |")
            lines.append("|----------|-------:|----------:|--------:|--------|----------:|")
            for r in regressed:
                lines.append(
                    f"| {r.variable} | {r.change_percent:+.1f}% "
                    f"| {r.baseline_value:.4g} | {r.current_value:.4g} "
                    f"| {r.method} | {r.threshold} |"
                )
        else:
            lines.append("**No regressions detected**\n")

        if passed:
            lines.append("")
            lines.append(
                f"*{len(passed)} variable(s) within threshold: "
                f"{', '.join(r.variable for r in passed)}*"
            )

        return "\n".join(lines)

    def append_to_report(self, report) -> None:
        """Append a formatted regression summary to a :class:`BenchReport`."""
        report.append_markdown(self.to_markdown(), name="Regression Report")

    def prepend_to_result(self, report, bench_res) -> None:
        """Insert a formatted regression summary at the top of *bench_res*'s tab."""
        import panel as pn

        md = pn.pane.Markdown(self.to_markdown(), name="Regression Report", width=800)
        report.prepend_to_result(bench_res, md)


def _clean_1d(a: np.ndarray) -> np.ndarray:
    """Flatten to 1-D float and remove NaNs."""
    flat = np.asarray(a, dtype=float).ravel()
    return flat[~np.isnan(flat)]


def _safe_change_percent(current: float, baseline: float) -> float:
    """Calculate percentage change, handling zero baseline gracefully."""
    if baseline == 0:
        if current == 0:
            return 0.0
        return float("inf") if current > 0 else float("-inf")
    return ((current - baseline) / abs(baseline)) * 100.0


def _is_regression(change_percent: float, direction: OptDir) -> bool:
    """Determine if a change constitutes a regression given the optimization direction."""
    if direction == OptDir.minimize:
        return change_percent > 0  # higher is worse
    if direction == OptDir.maximize:
        return change_percent < 0  # lower is worse
    return True  # OptDir.none — any significant change is a regression


def _exceeds_directional_threshold(
    change_percent: float,
    threshold_percent: float,
    direction: OptDir,
) -> bool:
    """Check if change exceeds threshold in the direction-appropriate sense."""
    if direction == OptDir.minimize:
        return change_percent > threshold_percent
    if direction == OptDir.maximize:
        return change_percent < -threshold_percent
    return abs(change_percent) > threshold_percent


def detect_percentage(
    variable: str,
    historical: np.ndarray,
    current: np.ndarray,
    threshold_percent: float = 5.0,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Compare current mean vs historical mean by percentage threshold."""
    hist_mean = float(np.nanmean(historical))
    curr_mean = float(np.nanmean(current))
    change = _safe_change_percent(curr_mean, hist_mean)

    exceeds = _exceeds_directional_threshold(change, threshold_percent, direction)
    regressed = exceeds and _is_regression(change, direction)

    frac = threshold_percent / 100.0
    return RegressionResult(
        variable=variable,
        method="percentage",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=threshold_percent,
        direction=direction.value,
        details=f"Change {change:+.2f}% vs threshold {threshold_percent}%",
        band_lower=hist_mean * (1.0 - frac),
        band_upper=hist_mean * (1.0 + frac),
    )


def detect_iqr(
    variable: str,
    historical_time_means: np.ndarray,
    current: np.ndarray,
    iqr_scale: float = 1.5,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """IQR outlier detection using per-time-point means from history.

    Args:
        variable: Name of the result variable being checked.
        historical_time_means: Array of per-time-point mean values from history.
        current: Current run values (will be averaged).
        iqr_scale: Multiplier for IQR to define outlier bounds (default 1.5).
        direction: Optimization direction from the result variable.
    """
    clean = _clean_1d(historical_time_means)
    curr_mean = float(np.nanmean(current))

    if len(clean) < 4:
        # Not enough time points for robust IQR; fall back to percentage using
        # the default percentage threshold so the comparison stays meaningful.
        return detect_percentage(
            variable,
            clean,
            current,
            threshold_percent=_METHOD_DEFAULTS["percentage"],
            direction=direction,
        )

    q1 = float(np.percentile(clean, 25))
    q3 = float(np.percentile(clean, 75))
    iqr = q3 - q1
    lower = q1 - iqr_scale * iqr
    upper = q3 + iqr_scale * iqr

    hist_mean = float(np.nanmean(clean))
    change = _safe_change_percent(curr_mean, hist_mean)

    outside_bounds = curr_mean > upper or curr_mean < lower
    regressed = outside_bounds and _is_regression(change, direction)

    return RegressionResult(
        variable=variable,
        method="iqr",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=iqr_scale,
        direction=direction.value,
        details=f"IQR bounds [{lower:.4g}, {upper:.4g}], current={curr_mean:.4g}",
        band_lower=lower,
        band_upper=upper,
    )


def detect_ttest(
    variable: str,
    historical: np.ndarray,
    current: np.ndarray,
    alpha: float = 0.05,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Welch's t-test between historical and current samples."""
    hist_clean = _clean_1d(historical)
    curr_clean = _clean_1d(current)

    if len(hist_clean) < 2 or len(curr_clean) < 2:
        # Fall back to percentage with alpha-based threshold
        return detect_percentage(
            variable, hist_clean, curr_clean, threshold_percent=alpha * 100, direction=direction
        )

    from scipy.stats import ttest_ind

    if direction == OptDir.minimize:
        alt = "greater"  # regression = current > historical
    elif direction == OptDir.maximize:
        alt = "less"  # regression = current < historical
    else:
        alt = "two-sided"

    stat, pvalue = ttest_ind(curr_clean, hist_clean, equal_var=False, alternative=alt)

    hist_mean = float(np.nanmean(hist_clean))
    curr_mean = float(np.nanmean(curr_clean))
    change = _safe_change_percent(curr_mean, hist_mean)
    regressed = pvalue < alpha

    return RegressionResult(
        variable=variable,
        method="ttest",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=alpha,
        direction=direction.value,
        details=f"t-stat={stat:.4g}, p-value={pvalue:.4g}, alpha={alpha}",
    )


def _robust_scale(values: np.ndarray) -> tuple[float, float]:
    """Return (median, MAD-based sigma) for a 1-D numeric array.

    The MAD is scaled by 1.4826 so it matches the standard deviation for
    Gaussian data.
    """
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, _MAD_TO_SIGMA * mad


def _residual_sigma(values: np.ndarray) -> float:
    """Estimate step-to-step noise via MAD of first differences.

    For data ``y[i] = trend[i] + eps[i]`` the diff ``y[i+1] - y[i]`` has variance
    ``2 * sigma^2``, so ``MAD(diff) * 1.4826 / sqrt(2)`` recovers sigma even
    when ``trend`` is non-stationary. This prevents a gradual drift from
    inflating its own noise estimate and masking itself.
    """
    if len(values) < 2:
        return 0.0
    diffs = np.diff(values)
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    return _MAD_TO_SIGMA * mad / np.sqrt(2.0)


def detect_adaptive(
    variable: str,
    historical_time_means: np.ndarray,
    current: np.ndarray,
    z_threshold: float = 3.5,
    drift_threshold: float | None = None,
    mk_alpha: float = 0.1,
    direction: OptDir = OptDir.minimize,
    historical_samples: np.ndarray | None = None,
) -> RegressionResult:
    """Robust regression detection combining step and drift tests.

    The method estimates the metric's inherent noise from history using a
    median + MAD (median absolute deviation) scale and expresses the current
    run's deviation in those noise units. Two orthogonal tests run in parallel:

    * **Short-term step** — flags if ``(current_mean - baseline) / noise_floor``
      exceeds ``z_threshold`` in the regression direction.
    * **Long-term drift** — fits a Theil–Sen slope on the historical time-point
      means (after a Hampel filter removes isolated outliers) and flags if the
      total projected drift, scaled by ``noise_floor``, exceeds
      ``drift_threshold`` and a Mann–Kendall test confirms monotonic trend
      with ``p < mk_alpha``.

    Args:
        variable: Name of the result variable being checked.
        historical_time_means: 1-D array of per-time-point mean values from
            history (one entry per prior run).
        current: Current run values (will be averaged).
        z_threshold: Step-test threshold in MAD-sigma units.
        drift_threshold: Drift-test threshold in MAD-sigma units. If ``None``,
            defaults to ``_DRIFT_FRAC * z_threshold`` so users need to tune
            only one knob.
        mk_alpha: Significance level for the Mann–Kendall trend guard.
        direction: Optimization direction from the result variable.
        historical_samples: Optional flat array of all historical samples
            (not per-time means). Used for the sparse-history fallback so the
            delegated ``ttest``/``percentage`` methods see the same input they
            would have received from ``detect_regressions`` directly. Falls
            back to ``historical_time_means`` when not provided.
    """
    if drift_threshold is None:
        drift_threshold = _DRIFT_FRAC * z_threshold

    hist_clean = _clean_1d(historical_time_means)
    curr_clean = _clean_1d(current)
    curr_mean = float(np.mean(curr_clean)) if len(curr_clean) else float("nan")

    # Not enough history for a robust scale — fall back to less strict checks.
    # Use the full per-sample history when available so the fallback behaves
    # like a direct call to detect_ttest/detect_percentage.
    if len(hist_clean) < 4:
        fallback_hist = (
            _clean_1d(historical_samples) if historical_samples is not None else hist_clean
        )
        if len(fallback_hist) >= 2 and len(curr_clean) >= 2:
            return detect_ttest(
                variable,
                fallback_hist,
                curr_clean,
                alpha=_METHOD_DEFAULTS["ttest"],
                direction=direction,
            )
        return detect_percentage(
            variable,
            fallback_hist,
            curr_clean,
            threshold_percent=_METHOD_DEFAULTS["percentage"],
            direction=direction,
        )

    baseline, mad_sigma = _robust_scale(hist_clean)
    noise_floor = max(mad_sigma, 1e-6 * abs(baseline), 1e-12)

    # Step test — current mean vs robust baseline in MAD-sigma units.
    z_step = (curr_mean - baseline) / noise_floor
    step_regressed = _is_regression(z_step, direction) and abs(z_step) > z_threshold

    # Drift test — Theil–Sen slope on Hampel-filtered history, MK significance.
    # Use residual (detrended) noise as the denominator so a real drift can't
    # inflate its own noise estimate and mask itself.
    deviations = np.abs(hist_clean - baseline)
    keep = deviations <= _HAMPEL_K * max(mad_sigma, 1e-12)
    filtered = hist_clean[keep] if keep.sum() >= 4 else hist_clean
    indices = np.arange(len(filtered), dtype=float)

    resid_sigma = _residual_sigma(filtered)
    drift_noise = max(resid_sigma, 1e-6 * abs(baseline), 1e-12)

    from scipy.stats import kendalltau, theilslopes

    slope = float(theilslopes(filtered, indices)[0])
    # Slope is per index-step; total drift across n points spans (n-1) steps.
    drift_total = slope * (len(filtered) - 1)
    z_drift = drift_total / drift_noise
    _, mk_p = kendalltau(indices, filtered)
    mk_p = float(mk_p) if not np.isnan(mk_p) else 1.0
    drift_regressed = (
        _is_regression(z_drift, direction) and abs(z_drift) > drift_threshold and mk_p < mk_alpha
    )

    regressed = step_regressed or drift_regressed

    change = _safe_change_percent(curr_mean, baseline)
    fired = []
    if step_regressed:
        fired.append("step")
    if drift_regressed:
        fired.append("drift")
    fired_str = "+".join(fired) if fired else "none"
    details = (
        f"fired={fired_str}, z_step={z_step:+.2f} (|z|>{z_threshold}), "
        f"z_drift={z_drift:+.2f} (|z|>{drift_threshold:.2f}), "
        f"mk_p={mk_p:.3g} (<{mk_alpha}), "
        f"baseline={baseline:.4g}, noise={noise_floor:.4g}"
    )

    return RegressionResult(
        variable=variable,
        method="adaptive",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=baseline,
        change_percent=change,
        threshold=z_threshold,
        direction=direction.value,
        details=details,
        band_lower=baseline - z_threshold * noise_floor,
        band_upper=baseline + z_threshold * noise_floor,
    )


def detect_regressions(dataset: xr.Dataset, bench_cfg, run_cfg) -> RegressionReport:
    """Run regression detection on a dataset with over_time dimension.

    For each numeric result variable, splits the dataset at the last over_time index,
    runs the configured detection method, and collects results into a report.

    Args:
        dataset: xarray Dataset with over_time dimension.
        bench_cfg: BenchCfg with result_vars list.
        run_cfg: BenchRunCfg with regression_method, regression_threshold.

    Returns:
        RegressionReport with results for each variable.
    """
    report = RegressionReport()

    if "over_time" not in dataset.dims:
        return report

    n_times = dataset.sizes["over_time"]
    if n_times < 2:
        return report

    method = run_cfg.regression_method
    threshold = run_cfg.regression_threshold

    # Use per-method default when no explicit threshold is provided.
    if threshold is None:
        threshold = _METHOD_DEFAULTS.get(method, 5.0)

    for rv in bench_cfg.result_vars:
        if not isinstance(rv, SCALAR_RESULT_TYPES):
            continue

        var_name = rv.name
        if var_name not in dataset:
            continue

        da = dataset[var_name]
        direction = rv.direction if hasattr(rv, "direction") else OptDir.none

        # Split: historical = all but last, current = last
        current_clean = _clean_1d(da.isel(over_time=-1).values)
        historical_clean = _clean_1d(da.isel(over_time=slice(None, -1)).values)

        if len(current_clean) == 0 or len(historical_clean) == 0:
            continue

        if method == "percentage":
            result = detect_percentage(
                var_name, historical_clean, current_clean, threshold, direction
            )
        elif method == "iqr":
            # Reduce all dims except over_time to get per-time-point means
            reduce_dims = [d for d in da.dims if d != "over_time"]
            time_means_arr = (
                da.isel(over_time=slice(None, -1))
                .mean(dim=reduce_dims, skipna=True)
                .values.astype(float)
            )
            result = detect_iqr(var_name, time_means_arr, current_clean, threshold, direction)
        elif method == "ttest":
            result = detect_ttest(var_name, historical_clean, current_clean, threshold, direction)
        elif method == "adaptive":
            reduce_dims = [d for d in da.dims if d != "over_time"]
            time_means_arr = (
                da.isel(over_time=slice(None, -1))
                .mean(dim=reduce_dims, skipna=True)
                .values.astype(float)
            )
            result = detect_adaptive(
                var_name,
                time_means_arr,
                current_clean,
                z_threshold=threshold,
                direction=direction,
                historical_samples=historical_clean,
            )
        else:
            logging.warning(f"Unknown regression method '{method}', falling back to percentage")
            result = detect_percentage(
                var_name, historical_clean, current_clean, threshold, direction
            )

        report.results.append(result)

    return report
