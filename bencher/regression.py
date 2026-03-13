"""Benchmark regression detection for over-time benchmarks.

Provides statistical methods to detect if benchmark values have changed
significantly between runs. Supports percentage threshold, IQR-based outlier
detection, and Welch's t-test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np
import xarray as xr

from bencher.variables.results import OptDir, ResultVar, ResultBool


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


@dataclass
class RegressionReport:
    """Aggregates regression results for all variables in a benchmark."""

    results: List[RegressionResult] = field(default_factory=list)

    @property
    def has_regressions(self) -> bool:
        return any(r.regressed for r in self.results)

    @property
    def regressed_variables(self) -> List[RegressionResult]:
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
    elif direction == OptDir.maximize:
        return change_percent < 0  # lower is worse
    else:  # OptDir.none
        return True  # any significant change is a regression


def detect_percentage(
    historical: np.ndarray,
    current: np.ndarray,
    threshold_percent: float = 5.0,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Compare current mean vs historical mean by percentage threshold."""
    hist_mean = float(np.nanmean(historical))
    curr_mean = float(np.nanmean(current))
    change = _safe_change_percent(curr_mean, hist_mean)

    if direction == OptDir.none:
        exceeds = abs(change) > threshold_percent
    elif direction == OptDir.minimize:
        exceeds = change > threshold_percent
    elif direction == OptDir.maximize:
        exceeds = change < -threshold_percent
    else:
        exceeds = abs(change) > threshold_percent

    regressed = exceeds and _is_regression(change, direction)

    return RegressionResult(
        variable="",
        method="percentage",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=threshold_percent,
        direction=str(direction),
        details=f"Change {change:+.2f}% vs threshold {threshold_percent}%",
    )


def detect_iqr(
    historical_time_means: np.ndarray,
    current: np.ndarray,
    iqr_scale: float = 1.5,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """IQR outlier detection using per-time-point means from history.

    Args:
        historical_time_means: Array of per-time-point mean values from history.
        current: Current run values (will be averaged).
        iqr_scale: Multiplier for IQR to define outlier bounds (default 1.5).
        direction: Optimization direction from the result variable.
    """
    clean = historical_time_means[~np.isnan(historical_time_means)]
    curr_mean = float(np.nanmean(current))

    if len(clean) < 4:
        # Fall back to percentage with iqr_scale as threshold
        return detect_percentage(
            clean, current, threshold_percent=iqr_scale * 10, direction=direction
        )

    q1 = float(np.percentile(clean, 25))
    q3 = float(np.percentile(clean, 75))
    iqr = q3 - q1
    lower = q1 - iqr_scale * iqr
    upper = q3 + iqr_scale * iqr

    hist_mean = float(np.nanmean(clean))
    change = _safe_change_percent(curr_mean, hist_mean)

    if direction == OptDir.minimize:
        exceeds = curr_mean > upper
    elif direction == OptDir.maximize:
        exceeds = curr_mean < lower
    else:
        exceeds = curr_mean > upper or curr_mean < lower

    regressed = exceeds

    return RegressionResult(
        variable="",
        method="iqr",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=iqr_scale,
        direction=str(direction),
        details=f"IQR bounds [{lower:.4g}, {upper:.4g}], current={curr_mean:.4g}",
    )


def detect_ttest(
    historical: np.ndarray,
    current: np.ndarray,
    alpha: float = 0.05,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Welch's t-test between historical and current samples."""
    hist_clean = historical[~np.isnan(historical)]
    curr_clean = current[~np.isnan(current)]

    if len(hist_clean) < 2 or len(curr_clean) < 2:
        # Fall back to percentage with alpha-based threshold
        return detect_percentage(
            hist_clean, curr_clean, threshold_percent=alpha * 100, direction=direction
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
        variable="",
        method="ttest",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=change,
        threshold=alpha,
        direction=str(direction),
        details=f"t-stat={stat:.4g}, p-value={pvalue:.4g}, alpha={alpha}",
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

    for rv in bench_cfg.result_vars:
        if not isinstance(rv, (ResultVar, ResultBool)):
            continue

        var_name = rv.name
        if var_name not in dataset:
            continue

        da = dataset[var_name]
        direction = rv.direction if hasattr(rv, "direction") else OptDir.none

        # Split: historical = all but last, current = last
        current_da = da.isel(over_time=-1)
        historical_da = da.isel(over_time=slice(None, -1))

        current_vals = current_da.values.flatten().astype(float)
        historical_vals = historical_da.values.flatten().astype(float)

        # Remove NaNs for validity check
        current_clean = current_vals[~np.isnan(current_vals)]
        historical_clean = historical_vals[~np.isnan(historical_vals)]

        if len(current_clean) == 0 or len(historical_clean) == 0:
            continue

        if method == "percentage":
            result = detect_percentage(historical_clean, current_clean, threshold, direction)
        elif method == "iqr":
            # Compute per-time-point means for IQR
            time_means = []
            for t in range(n_times - 1):
                t_vals = da.isel(over_time=t).values.flatten().astype(float)
                t_clean = t_vals[~np.isnan(t_vals)]
                if len(t_clean) > 0:
                    time_means.append(float(np.nanmean(t_clean)))
            time_means_arr = np.array(time_means)
            result = detect_iqr(time_means_arr, current_clean, threshold, direction)
        elif method == "ttest":
            result = detect_ttest(historical_clean, current_clean, threshold, direction)
        else:
            logging.warning(f"Unknown regression method '{method}', falling back to percentage")
            result = detect_percentage(historical_clean, current_clean, threshold, direction)

        result.variable = var_name
        report.results.append(result)

    return report
