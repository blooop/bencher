"""Benchmark regression detection for over-time benchmarks.

Provides a single statistical detector that flags significant changes between
a current run and historical runs. Noise is estimated in MAD-sigma units with
layered fallbacks (MAD → residual-MAD → discretization → relative floor), so
one function handles everything from noisy Gaussian history down to a single
prior sample.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import xarray as xr

from bencher.variables.results import OptDir, SCALAR_RESULT_TYPES

# Default step-test threshold in MAD-sigma units.
_DEFAULT_Z_THRESHOLD = 3.5

# Consistency factor so MAD estimates the standard deviation of a Gaussian.
_MAD_TO_SIGMA = 1.4826

# Drift threshold defaults to this fraction of z_threshold.
_DRIFT_FRAC = 0.85

# Hampel filter cutoff (in MAD units) used to drop outliers from the slope fit.
_HAMPEL_K = 5.0

# Mann–Kendall significance gate for the drift test.
_MK_ALPHA = 0.1

# Fallback floors when noise estimates collapse to zero.
_RELATIVE_FLOOR = 1e-6
_ABSOLUTE_FLOOR = 1e-12


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
    # Arrays retained so the result can be replotted without re-running detection.
    historical: np.ndarray | None = None
    current_samples: np.ndarray | None = None
    # x-axis coordinates for the historical and current points (typically the
    # ``over_time`` datetimes). Optional: falls back to integer indices.
    historical_x: np.ndarray | None = None
    current_x: np.ndarray | None = None

    def render_png(
        self,
        historical: np.ndarray | None = None,
        current: np.ndarray | float | None = None,
        path: str | Path | None = None,
        figsize: tuple[float, float] = (8.0, 5.0),
        dpi: int = 100,
    ) -> str:
        """Render this result as a diagnostic PNG (see :func:`render_regression_png`)."""
        return render_regression_png(
            self, historical=historical, current=current, path=path, figsize=figsize, dpi=dpi
        )

    def render_overlay(
        self,
        historical: np.ndarray | None = None,
        current: np.ndarray | float | None = None,
    ):
        """Build a :class:`holoviews.Overlay` of this result (see :func:`build_regression_overlay`)."""
        return build_regression_overlay(self, historical=historical, current=current)


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


def _regression_plot_spec(
    result: RegressionResult,
    historical: np.ndarray | None,
    current: np.ndarray | float | None,
) -> dict:
    """Prepare the data + styling used by both the matplotlib and holoviews renderers.

    Resolves the history and current arrays from the arguments first, falling
    back to anything stored on *result*. Returns a dict of primitives the
    backend-specific renderers consume. Keeping this shared guarantees the PNG
    and in-report plots stay in sync as the diagnostic evolves.
    """
    if historical is None:
        historical = result.historical if result.historical is not None else np.array([])
    hist = _clean_1d(np.asarray(historical, dtype=float))

    if current is None:
        current = result.current_samples
    if current is None:
        curr_samples = np.array([result.current_value], dtype=float)
    else:
        curr_samples = _clean_1d(np.asarray(current, dtype=float).ravel())
        if len(curr_samples) == 0:
            curr_samples = np.array([result.current_value], dtype=float)
    curr_mean = float(np.mean(curr_samples))

    # Use the recorded over_time coordinates when they line up with history
    # so the x-axis shows real timestamps. Non-numeric / non-datetime labels
    # (e.g. git_time_event strings) can't be combined with HSpan/HLine in
    # holoviews, so they fall back to integer indices with the labels
    # surfaced as tick overrides instead.
    hist_x: np.ndarray
    xticks: list[tuple[int, str]] | None = None
    if result.historical_x is not None and len(result.historical_x) == len(hist):
        raw_x = np.asarray(result.historical_x)
        if np.issubdtype(raw_x.dtype, np.number) or np.issubdtype(raw_x.dtype, np.datetime64):
            hist_x = raw_x
            xlabel = "time"
        else:
            hist_x = np.arange(len(hist))
            xticks = [(i, str(v)) for i, v in enumerate(raw_x)]
            xlabel = "time"
    else:
        hist_x = np.arange(len(hist))
        xlabel = "run index"

    # Pick x_current so its dtype matches hist_x. Mixing e.g. datetime64 and
    # int64 on the same axis raises in holoviews' range computation.
    current_x_arr = np.asarray(result.current_x) if result.current_x is not None else None
    if current_x_arr is not None:
        hist_is_dt = np.issubdtype(hist_x.dtype, np.datetime64)
        cur_is_dt = np.issubdtype(current_x_arr.dtype, np.datetime64)
        hist_is_num = np.issubdtype(hist_x.dtype, np.number)
        cur_is_num = np.issubdtype(current_x_arr.dtype, np.number)
        current_x_matches_hist = (hist_is_dt and cur_is_dt) or (hist_is_num and cur_is_num)
    else:
        current_x_matches_hist = False
    if current_x_matches_hist:
        x_current = current_x_arr
    elif current_x_arr is not None and xticks is not None:
        # String current_x — place it one step past the last history tick and
        # append it to the tick overrides.
        x_current = len(hist_x)
        xticks.append((x_current, str(result.current_x)))
    elif len(hist_x) > 0:
        # Extrapolate one step beyond the last history point.
        if np.issubdtype(hist_x.dtype, np.datetime64):
            if len(hist_x) >= 2:
                x_current = hist_x[-1] + (hist_x[-1] - hist_x[-2])
            else:
                # Single datetime point — nudge forward by a small timedelta so
                # the current marker doesn't overlap the history point exactly.
                x_current = hist_x[-1] + np.timedelta64(1, "s")
        else:
            x_current = hist_x[-1] + 1
    else:
        x_current = 0

    verdict_color = "#d62728" if result.regressed else "#2ca02c"
    verdict_label = "REGRESSED" if result.regressed else "OK"

    change_str = (
        f"{result.change_percent:+.1f}%"
        if np.isfinite(result.change_percent)
        else f"{result.change_percent}"
    )
    title = f"{result.variable} — {result.method} — {verdict_label}  (Δ {change_str})"

    return {
        "hist": hist,
        "hist_x": hist_x,
        "xticks": xticks,
        "curr_samples": curr_samples,
        "curr_mean": curr_mean,
        "x_current": x_current,
        "band": (
            (result.band_lower, result.band_upper)
            if result.band_lower is not None and result.band_upper is not None
            else None
        ),
        "baseline": result.baseline_value,
        "verdict_color": verdict_color,
        "title": title,
        "xlabel": xlabel,
        "ylabel": result.variable,
    }


def build_regression_overlay(
    result: RegressionResult,
    historical: np.ndarray | None = None,
    current: np.ndarray | float | None = None,
    width: int = 700,
    height: int = 350,
):
    """Build a :class:`holoviews.Overlay` diagnostic of a regression result.

    Uses the same logic as :func:`render_regression_png` but returns a
    backend-agnostic holoviews object, so the same plot can be embedded in an
    HTML report (bokeh backend) or saved as a PNG (matplotlib backend).

    Args:
        result: The :class:`RegressionResult` to visualise.
        historical: Optional 1-D array of historical per-time-point means.
            Falls back to ``result.historical`` if omitted.
        current: Optional current-run sample array (or scalar). Falls back to
            ``result.current_samples`` / ``result.current_value``.
        width, height: Pixel dimensions passed to the overlay's ``opts``.
    """
    import holoviews as hv

    spec = _regression_plot_spec(result, historical, current)
    hist = spec["hist"]
    hist_x = spec["hist_x"]
    verdict_color = spec["verdict_color"]
    x_current = spec["x_current"]

    # Build an explicit x range so band/baseline render correctly regardless
    # of whether the x-axis is numeric, datetime, or categorical (xticks).
    x_start = hist_x[0] if len(hist_x) > 0 else x_current
    x_end = x_current

    layers = []
    if spec["band"] is not None:
        lo, hi = spec["band"]
        layers.append(
            hv.Area(
                ([x_start, x_end], [lo, lo], [hi, hi]),
                kdims=[spec["xlabel"]],
                vdims=[spec["ylabel"], "band_upper"],
            ).opts(color=verdict_color, alpha=0.10, line_alpha=0)
        )
    layers.append(
        hv.Curve(
            [(x_start, spec["baseline"]), (x_end, spec["baseline"])],
            spec["xlabel"],
            spec["ylabel"],
        ).opts(color="#555555", line_dash="dashed", line_width=1)
    )
    if len(hist) > 0:
        layers.append(
            hv.Curve(list(zip(hist_x, hist)), spec["xlabel"], spec["ylabel"]).opts(
                color="#1f77b4", line_width=1.5
            )
        )
        # Dotted connector from the last history point to the current marker
        # so the jump that triggered the regression is visually obvious.
        layers.append(
            hv.Curve(
                [(hist_x[-1], hist[-1]), (x_current, spec["curr_mean"])],
                spec["xlabel"],
                spec["ylabel"],
            ).opts(color=verdict_color, line_dash="dotted", line_width=1.5)
        )
    if len(spec["curr_samples"]) > 1:
        layers.append(
            hv.Scatter(
                [(x_current, v) for v in spec["curr_samples"]],
                spec["xlabel"],
                spec["ylabel"],
            ).opts(color=verdict_color, alpha=0.35, size=5)
        )
    layers.append(
        hv.Scatter(
            [(x_current, spec["curr_mean"])],
            spec["xlabel"],
            spec["ylabel"],
        ).opts(color=verdict_color, size=10, line_color="black", line_width=1)
    )

    overlay = layers[0]
    for layer in layers[1:]:
        overlay = overlay * layer

    opts_kwargs = dict(title=spec["title"], width=width, height=height, show_grid=True)
    if spec["xticks"] is not None:
        opts_kwargs["xticks"] = spec["xticks"]
        opts_kwargs["xrotation"] = 30
    return overlay.opts(**opts_kwargs)


def render_regression_png(
    result: RegressionResult,
    historical: np.ndarray | None = None,
    current: np.ndarray | float | None = None,
    path: str | Path | None = None,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 100,
) -> str:
    """Render a diagnostic PNG of a regression result using matplotlib.

    The plot contains everything needed to diagnose the *style* of regression
    at a glance — history time-series (to reveal drift and noise), the baseline
    line, the acceptance band (to reveal step size), and the current-run marker
    coloured by the pass/fail verdict.

    Args:
        result: The :class:`RegressionResult` produced by :func:`detect_regression`.
        historical: 1-D array of the historical per-time-point means. Pass an
            empty array if no history is available — only the current marker,
            baseline, and band are drawn in that case.
        current: Current-run sample(s). If ``None``, ``result.current_value``
            is used. If given an array, the per-sample spread is shown as a
            vertical strip alongside the mean marker.
        path: Output PNG path. If ``None``, a path is generated via
            :func:`bencher.utils.gen_image_path` so the file lives under the
            bencher cache directory.
        figsize: Matplotlib figure size in inches.
        dpi: Output DPI (800x500 at ``dpi=100`` works well for GitHub comments).

    Returns:
        Absolute path to the saved PNG as a string.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    if path is None:
        from bencher.utils import gen_image_path

        path = gen_image_path(f"regression_{result.variable}")
    path_str = str(path)

    spec = _regression_plot_spec(result, historical, current)
    hist = spec["hist"]
    hist_x = spec["hist_x"]
    curr_samples = spec["curr_samples"]
    x_current = spec["x_current"]
    verdict_color = spec["verdict_color"]

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.88, bottom=0.2)

    if spec["band"] is not None:
        lo, hi = spec["band"]
        ax.axhspan(lo, hi, color=verdict_color, alpha=0.10, label="acceptance band")

    ax.axhline(
        spec["baseline"],
        color="#555555",
        linestyle="--",
        linewidth=1.0,
        label=f"baseline={spec['baseline']:.3g}",
    )

    if len(hist) > 0:
        ax.plot(
            hist_x,
            hist,
            "-o",
            color="#1f77b4",
            markersize=3.5,
            linewidth=1.2,
            label="history",
        )
        ax.plot(
            [hist_x[-1], x_current],
            [hist[-1], spec["curr_mean"]],
            linestyle=":",
            color=verdict_color,
            linewidth=1.2,
            alpha=0.8,
        )

    if len(curr_samples) > 1:
        ax.scatter(
            [x_current] * len(curr_samples),
            curr_samples,
            color=verdict_color,
            alpha=0.35,
            s=18,
        )
    ax.scatter(
        [x_current],
        [spec["curr_mean"]],
        color=verdict_color,
        s=70,
        zorder=5,
        edgecolor="black",
        linewidth=0.7,
        label=f"current={spec['curr_mean']:.3g}",
    )

    ax.margins(x=0.08)

    ax.set_xlabel(spec["xlabel"])
    ax.set_ylabel(spec["ylabel"])
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.set_title(spec["title"], color=verdict_color, fontsize=10, fontweight="bold")
    ax.legend(loc="upper left", fontsize=7, framealpha=0.85, ncol=2)

    if spec["xticks"] is not None:
        ticks, labels = zip(*spec["xticks"])
        ax.set_xticks(list(ticks))
        ax.set_xticklabels(list(labels), rotation=30, ha="right")
    elif len(hist_x) > 0 and np.issubdtype(np.asarray(hist_x).dtype, np.datetime64):
        fig.autofmt_xdate(rotation=30)

    fig.savefig(path_str, dpi=dpi)
    plt.close(fig)
    return path_str


def _clean_1d(a: np.ndarray) -> np.ndarray:
    """Flatten to 1-D float and remove NaNs."""
    flat = np.asarray(a, dtype=float).ravel()
    return flat[~np.isnan(flat)]


def _safe_change_percent(current: float, baseline: float) -> float:
    """Calculate percentage change, handling zero baseline gracefully."""
    if not np.isfinite(current) or not np.isfinite(baseline):
        return float("nan")
    if baseline == 0:
        if current == 0:
            return 0.0
        return float("inf") if current > 0 else float("-inf")
    return ((current - baseline) / abs(baseline)) * 100.0


def _is_regression(delta: float, direction: OptDir) -> bool:
    """Return True if *delta* (a signed z-score) worsens the metric."""
    if direction == OptDir.minimize:
        return delta > 0  # higher is worse
    if direction == OptDir.maximize:
        return delta < 0  # lower is worse
    return True  # OptDir.none — any significant change is a regression


def _robust_scale(values: np.ndarray) -> tuple[float, float]:
    """Return (median, MAD-based sigma) for a 1-D numeric array."""
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, _MAD_TO_SIGMA * mad


def _residual_sigma(values: np.ndarray) -> float:
    """Estimate step-to-step noise via MAD of first differences.

    For data ``y[i] = trend[i] + eps[i]`` the diff ``y[i+1] - y[i]`` has variance
    ``2 * sigma^2``, so ``MAD(diff) * 1.4826 / sqrt(2)`` recovers sigma even
    when ``trend`` is non-stationary.
    """
    if len(values) < 2:
        return 0.0
    diffs = np.diff(values)
    mad = float(np.median(np.abs(diffs - np.median(diffs))))
    return _MAD_TO_SIGMA * mad / np.sqrt(2.0)


def _discretization_floor(values: np.ndarray) -> float:
    """Smallest non-zero absolute step between successive history values.

    For integer-valued metrics this is at least 1, providing a meaningful
    noise floor when both MAD and residual-MAD collapse to zero (constant
    history). Returns 0 when no non-zero steps exist.
    """
    if len(values) < 2:
        return 0.0
    diffs = np.abs(np.diff(values))
    non_zero = diffs[diffs > 0]
    return float(np.min(non_zero)) if len(non_zero) else 0.0


def _estimate_noise(values: np.ndarray, baseline: float) -> tuple[float, str]:
    """Estimate noise in a 1-D history with layered fallbacks.

    Returns ``(noise, source)`` where *source* names the layer that produced
    the estimate: ``"mad"`` → ``"residual"`` → ``"discretization"`` → ``"floor"``.
    The final result is always clamped to at least ``_RELATIVE_FLOOR * |baseline|``
    (and an absolute floor of ``_ABSOLUTE_FLOOR``) so divisions never explode.
    """
    rel_floor = max(_RELATIVE_FLOOR * abs(baseline), _ABSOLUTE_FLOOR)

    if len(values) >= 2:
        _, mad_sigma = _robust_scale(values)
        if mad_sigma > 0:
            return max(mad_sigma, rel_floor), "mad"
        resid = _residual_sigma(values)
        if resid > 0:
            return max(resid, rel_floor), "residual"
        disc = _discretization_floor(values)
        if disc > 0:
            return max(disc, rel_floor), "discretization"
    return rel_floor, "floor"


def detect_regression(
    variable: str,
    historical: np.ndarray,
    current: np.ndarray,
    *,
    z_threshold: float = _DEFAULT_Z_THRESHOLD,
    min_change_percent: float | None = None,
    direction: OptDir = OptDir.minimize,
    historical_time_means: np.ndarray | None = None,
    drift_threshold: float | None = None,
) -> RegressionResult:
    """Detect a regression in a metric using robust step and drift tests.

    Noise is estimated in MAD-sigma units with layered fallbacks so the same
    function handles everything from long noisy history down to a single prior
    sample. The step test always runs. The drift test runs whenever
    *historical_time_means* is provided and has at least 4 entries.

    Args:
        variable: Name of the result variable.
        historical: Flat 1-D array of all historical samples.
        current: Current-run samples (will be averaged).
        z_threshold: Step-test threshold in MAD-sigma units.
        min_change_percent: Optional AND-guard — even if ``|z| > z_threshold``,
            require ``|percent change| >= min_change_percent`` before flagging.
            Useful for stable metrics where the noise floor collapses to the
            relative floor and a single-unit change yields a huge z-score.
            Set to ``None`` (default) to disable.
        direction: Optimization direction from the result variable.
        historical_time_means: Optional 1-D array of per-time-point means
            (one entry per prior time step). When provided with ≥4 entries a
            drift test runs alongside the step test.
        drift_threshold: Drift-test threshold in MAD-sigma units. If ``None``,
            defaults to ``0.85 * z_threshold`` so users tune only one knob.
    """
    hist_clean = _clean_1d(historical)
    curr_clean = _clean_1d(current)

    if len(curr_clean) == 0:
        curr_mean = float("nan")
    elif len(curr_clean) == 1:
        curr_mean = float(curr_clean[0])
    else:
        curr_mean = float(np.mean(curr_clean))

    if len(hist_clean) >= 2:
        baseline, _ = _robust_scale(hist_clean)
    elif len(hist_clean) == 1:
        baseline = float(hist_clean[0])
    else:
        baseline = float("nan")

    noise_floor, noise_source = _estimate_noise(hist_clean, baseline)

    change = _safe_change_percent(curr_mean, baseline)
    if min_change_percent is None:
        percent_ok = True
    elif not np.isfinite(change):
        # change is inf (zero baseline, nonzero current) or nan — the guard
        # can't meaningfully compare a percent change, so treat as unsatisfied.
        percent_ok = False
    else:
        percent_ok = abs(change) >= min_change_percent

    # Step test
    if np.isfinite(curr_mean) and np.isfinite(baseline):
        z_step = (curr_mean - baseline) / noise_floor
    else:
        z_step = 0.0
    step_regressed = _is_regression(z_step, direction) and abs(z_step) > z_threshold and percent_ok

    # Drift test (optional)
    drift_thresh = _DRIFT_FRAC * z_threshold if drift_threshold is None else drift_threshold
    z_drift = 0.0
    mk_p = 1.0
    drift_regressed = False

    if historical_time_means is not None:
        tm = _clean_1d(historical_time_means)
        if len(tm) >= 4:
            tm_baseline, tm_mad = _robust_scale(tm)
            deviations = np.abs(tm - tm_baseline)
            keep = deviations <= _HAMPEL_K * max(tm_mad, 1e-12)
            filtered = tm[keep] if keep.sum() >= 4 else tm
            indices = np.arange(len(filtered), dtype=float)
            resid = _residual_sigma(filtered)
            drift_noise = max(resid, _RELATIVE_FLOOR * abs(tm_baseline), _ABSOLUTE_FLOOR)

            from scipy.stats import kendalltau, theilslopes

            slope = float(theilslopes(filtered, indices)[0])
            drift_total = slope * (len(filtered) - 1)
            z_drift = drift_total / drift_noise
            _, mk_p = kendalltau(indices, filtered)
            mk_p = float(mk_p) if not np.isnan(mk_p) else 1.0
            drift_regressed = (
                _is_regression(z_drift, direction)
                and abs(z_drift) > drift_thresh
                and mk_p < _MK_ALPHA
                and percent_ok
            )

    # Cast to plain Python bool — xarray comparisons return np.bool_ which
    # fails strict `is True`/`is False` identity checks.
    regressed = bool(step_regressed or drift_regressed)

    fired = []
    if step_regressed:
        fired.append("step")
    if drift_regressed:
        fired.append("drift")
    fired_str = "+".join(fired) if fired else "none"
    guard_str = f", min%={min_change_percent}" if min_change_percent is not None else ""
    details = (
        f"fired={fired_str}, z_step={z_step:+.2f} (|z|>{z_threshold}), "
        f"z_drift={z_drift:+.2f} (|z|>{drift_thresh:.2f}), "
        f"mk_p={mk_p:.3g} (<{_MK_ALPHA}), "
        f"baseline={baseline:.4g}, noise={noise_floor:.4g} ({noise_source})"
        f"{guard_str}"
    )

    if np.isfinite(baseline):
        band_lower = baseline - z_threshold * noise_floor
        band_upper = baseline + z_threshold * noise_floor
    else:
        band_lower = None
        band_upper = None

    return RegressionResult(
        variable=variable,
        method="regression",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=baseline,
        change_percent=change,
        threshold=z_threshold,
        direction=direction.value,
        details=details,
        band_lower=band_lower,
        band_upper=band_upper,
    )


def detect_regressions(dataset: xr.Dataset, bench_cfg, run_cfg) -> RegressionReport:
    """Run regression detection on a dataset with ``over_time`` dimension.

    For each numeric result variable, splits the dataset at the last over_time
    index, runs :func:`detect_regression`, and collects results into a report.

    Args:
        dataset: xarray Dataset with over_time dimension.
        bench_cfg: BenchCfg with result_vars list.
        run_cfg: BenchRunCfg with ``regression_threshold`` (z-score) and
            ``regression_min_change_percent``.

    Returns:
        RegressionReport with results for each variable.
    """
    report = RegressionReport()

    if "over_time" not in dataset.dims:
        return report

    n_times = dataset.sizes["over_time"]
    if n_times < 2:
        return report

    threshold = run_cfg.regression_threshold
    if threshold is None:
        threshold = _DEFAULT_Z_THRESHOLD
    min_change_percent = getattr(run_cfg, "regression_min_change_percent", None)

    for rv in bench_cfg.result_vars:
        if not isinstance(rv, SCALAR_RESULT_TYPES):
            continue

        var_name = rv.name
        if var_name not in dataset:
            continue

        da = dataset[var_name]
        direction = rv.direction if hasattr(rv, "direction") else OptDir.none

        current_clean = _clean_1d(da.isel(over_time=-1).values)
        historical_clean = _clean_1d(da.isel(over_time=slice(None, -1)).values)

        if len(current_clean) == 0 or len(historical_clean) == 0:
            continue

        reduce_dims = [d for d in da.dims if d != "over_time"]
        time_means_arr = (
            da.isel(over_time=slice(None, -1))
            .mean(dim=reduce_dims, skipna=True)
            .values.astype(float)
        )

        result = detect_regression(
            var_name,
            historical_clean,
            current_clean,
            z_threshold=threshold,
            min_change_percent=min_change_percent,
            direction=direction,
            historical_time_means=time_means_arr,
        )

        time_coord = dataset["over_time"].values
        result.historical = time_means_arr
        result.historical_x = time_coord[:-1]
        result.current_x = time_coord[-1]
        result.current_samples = current_clean

        report.results.append(result)

    return report
