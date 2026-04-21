"""Benchmark regression detection for over-time benchmarks.

Provides statistical methods to detect if benchmark values have changed
significantly between runs. Supports a percentage threshold and an
adaptive MAD-based detector with an optional percent floor for dual-band
suppression.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import xarray as xr

from bencher.variables.results import OptDir, SCALAR_RESULT_TYPES

# Default thresholds per method — used when the user hasn't explicitly set a threshold.
_METHOD_DEFAULTS = {
    "percentage": 10.0,  # percent change
    "adaptive": 3.5,  # robust z-score threshold in MAD units
}

# Consistency factor so MAD estimates the standard deviation of a Gaussian.
_MAD_TO_SIGMA = 1.4826

# Drift threshold defaults to this fraction of regression_mad when not set by caller.
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
    # Optional second acceptance band (dual-band adaptive). When both bands are
    # populated a value must lie outside BOTH to count as a regression.
    percent_band_lower: float | None = None
    percent_band_upper: float | None = None
    # Arrays retained so the result can be replotted without re-running detection.
    historical: np.ndarray | None = None
    current_samples: np.ndarray | None = None
    # Optional per-sample historical data (flat: all repeats from all historical
    # time points) with paired x-coords — used to render a scatter overlay
    # showing the full spread at each time point, not just the per-time mean.
    historical_all: np.ndarray | None = None
    historical_all_x: np.ndarray | None = None
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

    baseline = result.baseline_value

    def _clip(band: tuple[float, float] | None) -> tuple[float, float] | None:
        """Clip the band to the side(s) that actually gate regressions.

        Stored bands are symmetric around the baseline, but for directional
        metrics only one side flags a regression. Minimize only trips on
        values above baseline; maximize only trips on values below. None
        flags either side, so the full symmetric band stays."""
        if band is None:
            return None
        lo, hi = band
        if result.direction == OptDir.minimize.value:
            return (baseline, hi)
        if result.direction == OptDir.maximize.value:
            return (lo, baseline)
        return (lo, hi)

    mad_band = (
        _clip((result.band_lower, result.band_upper))
        if result.band_lower is not None and result.band_upper is not None
        else None
    )
    pct_band = (
        _clip((result.percent_band_lower, result.percent_band_upper))
        if result.percent_band_lower is not None and result.percent_band_upper is not None
        else None
    )

    # Shared declarative band layers — both matplotlib and holoviews iterate
    # this list so the two backends render the same thing by construction.
    # Each entry is (lo, hi, color, alpha, label). The acceptance band always
    # shades green: it represents the *valid* region, not the pass/fail
    # verdict (verdict colouring lives on the current marker + connector).
    valid_color = "#2ca02c"
    # Light blue for the secondary (percentage) band — clearly distinct from
    # the green MAD band after alpha blending, and distinct from the darker
    # blue (#1f77b4) used for the history line so it doesn't read as part of
    # the data series.
    valid_color_light = "#6baed6"
    band_layers: list[tuple[float, float, str, float, str]] = []
    if mad_band is not None and pct_band is not None:
        band_layers.append((mad_band[0], mad_band[1], valid_color, 0.15, "MAD band"))
        band_layers.append((pct_band[0], pct_band[1], valid_color_light, 0.15, "percentage band"))
    elif mad_band is not None:
        band_layers.append((mad_band[0], mad_band[1], valid_color, 0.15, "acceptance band"))
    elif pct_band is not None:
        band_layers.append((pct_band[0], pct_band[1], valid_color, 0.15, "acceptance band"))

    # Per-sample historical scatter: mirrors the current-run alpha scatter so
    # history and current use the same visual language. Prefer per-repeat data
    # when available (populated by detect_regressions); otherwise fall back to
    # the per-time mean array itself so direct detect_* calls still get dots.
    # Works even on categorical x-axes (string labels → integer xticks) as
    # long as historical_all_x is numeric and aligned with the integer hist_x
    # positions that back the tick labels.
    hist_scatter_x: np.ndarray | None = None
    hist_scatter_y: np.ndarray | None = None
    if (
        result.historical_all is not None
        and result.historical_all_x is not None
        and len(result.historical_all) == len(result.historical_all_x)
        and len(result.historical_all) > 0
    ):
        raw = np.asarray(result.historical_all_x)
        hist_is_dt = np.issubdtype(hist_x.dtype, np.datetime64)
        raw_is_dt = np.issubdtype(raw.dtype, np.datetime64)
        hist_is_num = np.issubdtype(hist_x.dtype, np.number)
        raw_is_num = np.issubdtype(raw.dtype, np.number)
        if (hist_is_dt and raw_is_dt) or (hist_is_num and raw_is_num):
            hist_scatter_x = raw
            hist_scatter_y = np.asarray(result.historical_all, dtype=float)
    if hist_scatter_x is None and len(hist) > 0 and xticks is None:
        hist_scatter_x = hist_x
        hist_scatter_y = hist

    return {
        "hist": hist,
        "hist_x": hist_x,
        "hist_scatter_x": hist_scatter_x,
        "hist_scatter_y": hist_scatter_y,
        "xticks": xticks,
        "curr_samples": curr_samples,
        "curr_mean": curr_mean,
        "x_current": x_current,
        "band_layers": band_layers,
        "baseline": result.baseline_value,
        "verdict_color": verdict_color,
        "title": title,
        "xlabel": xlabel,
        "ylabel": result.variable,
    }


def _ensure_matplotlib_backend_loaded() -> None:
    """Register the holoviews matplotlib backend without changing the default.

    render_regression_png needs matplotlib to export a PNG, but the report path
    uses bokeh — calling hv.extension('matplotlib') naively would flip the
    global default mid-run. This loads the renderer if missing, then restores
    the prior default. Selects the non-interactive Agg backend when no
    matplotlib backend has been configured yet (``force=False``), so holoviews
    doesn't pick up Tk/Qt on a fresh process (which leaks ``main thread is not
    in main loop`` tracebacks at interpreter shutdown). If the caller has
    already configured a backend (e.g., Jupyter's inline backend), that choice
    is left alone.
    """
    import matplotlib

    matplotlib.use("Agg", force=False)

    import holoviews as hv

    if "matplotlib" in hv.Store.renderers:
        return
    prev_backend = hv.Store.current_backend
    hv.extension("matplotlib", logo=False)
    if prev_backend and hv.Store.current_backend != prev_backend:
        hv.Store.set_current_backend(prev_backend)


def build_regression_overlay(
    result: RegressionResult,
    historical: np.ndarray | None = None,
    current: np.ndarray | float | None = None,
    width: int = 700,
    height: int = 350,
    fig_inches: tuple[float, float] = (7.0, 3.5),
):
    """Build a :class:`holoviews.Overlay` diagnostic of a regression result.

    Opts are applied per-backend so the same overlay renders correctly under
    both bokeh (for embedded HTML reports) and matplotlib (for PNG export via
    :func:`render_regression_png`). History always shows as mean line + raw
    alpha scatter; regression-specific layers (acceptance band, baseline,
    verdict-coloured current marker) are conditional on the data in *result*.

    Args:
        result: The :class:`RegressionResult` to visualise.
        historical: Optional 1-D array of historical per-time-point means.
            Falls back to ``result.historical`` if omitted.
        current: Optional current-run sample array (or scalar). Falls back to
            ``result.current_samples`` / ``result.current_value``.
        width, height: Pixel dimensions for the bokeh backend.
        fig_inches: Figure size in inches for the matplotlib backend.
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

    # Each element duplicates its style opts across both backends so they
    # apply regardless of which renderer is active — holoviews does NOT
    # carry no-backend opts across backend boundaries, so omitting the
    # backend kwarg silently drops styles like alpha when rendering as PNG.
    # Elements whose identity matters for the legend carry a ``label`` kwarg;
    # decorative layers (hist-sample scatter, current-sample scatter, dotted
    # connector) are label-less so the legend stays compact.
    layers = []
    for lo, hi, color, alpha, label in spec["band_layers"]:
        # Holoviews' matplotlib backend silently drops ``color`` opts on
        # hv.Area (Curve/Scatter honour it, Area does not), which made every
        # band render in whatever matplotlib colour-cycled next — so a
        # non-regressed acceptance band rendered pink. Setting facecolor on
        # the PolyCollection via a hook is the only path that actually sticks.
        def _area_color_hook(plot, _element, _fc=color, _alpha=alpha):
            artist = plot.handles.get("artist")
            if artist is not None:
                artist.set_facecolor(_fc)
                artist.set_edgecolor("none")
                artist.set_alpha(_alpha)

        layers.append(
            hv.Area(
                ([x_start, x_end], [lo, lo], [hi, hi]),
                kdims=[spec["xlabel"]],
                vdims=[spec["ylabel"], "band_upper"],
                label=label,
            ).opts(
                hv.opts.Area(backend="bokeh", color=color, alpha=alpha, line_alpha=0),
                hv.opts.Area(backend="matplotlib", hooks=[_area_color_hook]),
            )
        )
    layers.append(
        hv.Curve(
            [(x_start, spec["baseline"]), (x_end, spec["baseline"])],
            spec["xlabel"],
            spec["ylabel"],
            label=f"baseline={spec['baseline']:.3g}",
        ).opts(
            hv.opts.Curve(
                backend="bokeh",
                color="#555555",
                alpha=0.7,
                line_dash="dashed",
                line_width=1,
            ),
            hv.opts.Curve(
                backend="matplotlib",
                color="#555555",
                alpha=0.7,
                linestyle="--",
                linewidth=1,
            ),
        )
    )
    if spec["hist_scatter_x"] is not None and spec["hist_scatter_y"] is not None:
        layers.append(
            hv.Scatter(
                list(zip(spec["hist_scatter_x"], spec["hist_scatter_y"])),
                spec["xlabel"],
                spec["ylabel"],
            ).opts(
                hv.opts.Scatter(
                    backend="bokeh",
                    color="#1f77b4",
                    alpha=0.35,
                    size=3,
                    show_legend=False,
                ),
                hv.opts.Scatter(
                    backend="matplotlib",
                    color="#1f77b4",
                    alpha=0.35,
                    s=8,
                    show_legend=False,
                ),
            )
        )
    if len(hist) > 0:
        layers.append(
            hv.Curve(
                list(zip(hist_x, hist)),
                spec["xlabel"],
                spec["ylabel"],
                label="history",
            ).opts(
                hv.opts.Curve(backend="bokeh", color="#1f77b4", alpha=0.7, line_width=1.5),
                hv.opts.Curve(backend="matplotlib", color="#1f77b4", alpha=0.7, linewidth=1.2),
            )
        )
        # Dotted connector from the last history point to the current marker
        # so the jump that triggered the regression is visually obvious.
        layers.append(
            hv.Curve(
                [(hist_x[-1], hist[-1]), (x_current, spec["curr_mean"])],
                spec["xlabel"],
                spec["ylabel"],
            ).opts(
                hv.opts.Curve(
                    backend="bokeh",
                    color=verdict_color,
                    alpha=0.8,
                    line_dash="dotted",
                    line_width=1.5,
                    show_legend=False,
                ),
                hv.opts.Curve(
                    backend="matplotlib",
                    color=verdict_color,
                    alpha=0.8,
                    linestyle=":",
                    linewidth=1.2,
                    show_legend=False,
                ),
            )
        )
    if len(spec["curr_samples"]) > 1:
        layers.append(
            hv.Scatter(
                [(x_current, v) for v in spec["curr_samples"]],
                spec["xlabel"],
                spec["ylabel"],
            ).opts(
                hv.opts.Scatter(
                    backend="bokeh",
                    color=verdict_color,
                    alpha=0.35,
                    size=5,
                    show_legend=False,
                ),
                hv.opts.Scatter(
                    backend="matplotlib",
                    color=verdict_color,
                    alpha=0.35,
                    s=18,
                    show_legend=False,
                ),
            )
        )
    layers.append(
        hv.Scatter(
            [(x_current, spec["curr_mean"])],
            spec["xlabel"],
            spec["ylabel"],
            label=f"current={spec['curr_mean']:.3g}",
        ).opts(
            hv.opts.Scatter(
                backend="bokeh",
                color=verdict_color,
                size=10,
                line_color="black",
                line_width=1,
            ),
            hv.opts.Scatter(
                backend="matplotlib",
                color=verdict_color,
                s=70,
                edgecolors="black",
                linewidth=0.7,
            ),
        )
    )

    overlay = layers[0]
    for layer in layers[1:]:
        overlay = overlay * layer

    # Compact font sizing — the PNGs render at ~4–9 inches wide so the default
    # matplotlib font sizes overflow the figure. Bokeh accepts the same dict.
    fontsize = {"title": 9, "labels": 8, "xticks": 6, "yticks": 7, "legend": 6}

    # holoviews' matplotlib backend defaults to a square data aspect, centers a
    # small axes inside the figure, and drops Element ``label=`` on Area/Curve
    # overlays so its own legend only shows a subset of layers. The hooks below
    # stretch the axes, set the title manually, and build a proxy legend from
    # the spec so every rendered layer can appear in the legend.
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    title = spec["title"]
    baseline = spec["baseline"]
    hist_len = len(hist)
    legend_entries: list = []
    for lo, hi, color, alpha, band_label in spec["band_layers"]:
        legend_entries.append(Patch(facecolor=color, alpha=alpha, label=band_label))
    legend_entries.append(
        Line2D([], [], color="#555555", alpha=0.7, linestyle="--", label=f"baseline={baseline:.3g}")
    )
    if hist_len > 0:
        legend_entries.append(Line2D([], [], color="#1f77b4", alpha=0.7, label="history"))
    legend_entries.append(
        Line2D(
            [],
            [],
            marker="o",
            linestyle="",
            color=verdict_color,
            markersize=7,
            markeredgecolor="black",
            markeredgewidth=0.7,
            label=f"current={spec['curr_mean']:.3g}",
        )
    )

    legend_handles = tuple(legend_entries)

    def _fill_fig_hook(
        plot,
        _element,
        _title=title,
        _title_color=verdict_color,
        _title_fs=fontsize["title"],
        _legend_fs=fontsize["legend"],
        _legend=legend_handles,
    ):
        ax = plot.handles["axis"]
        ax.set_aspect("auto")
        # left 0.15 leaves room for y-label + ticks, top 0.86 leaves room for
        # the title, bottom 0.22 leaves room for rotated xtick labels.
        ax.set_position([0.15, 0.22, 0.82, 0.64])
        ax.set_title(_title, color=_title_color, fontsize=_title_fs, fontweight="bold")
        ax.legend(
            handles=_legend,
            loc="upper left",
            fontsize=_legend_fs,
            framealpha=0.85,
            ncol=2,
            handlelength=1.2,
            borderpad=0.3,
            labelspacing=0.3,
        )

    mpl_hooks = [_fill_fig_hook]
    overlay_opts = [
        hv.opts.Overlay(title=spec["title"], show_grid=True, show_legend=True, fontsize=fontsize),
        hv.opts.Overlay(
            backend="bokeh",
            width=width,
            height=height,
            legend_position="top_left",
        ),
    ]
    if spec["xticks"] is not None:
        # bokeh accepts [(pos, label), ...] directly; matplotlib silently
        # ignores the label half and falls back to integer tick text, so
        # labels have to be pushed in via a plot hook on that backend.
        xticks_pairs = spec["xticks"]
        xtick_fontsize = fontsize["xticks"]

        def _mpl_xticks_hook(plot, _element, _pairs=xticks_pairs, _fs=xtick_fontsize):
            ax = plot.handles["axis"]
            positions = [p for p, _ in _pairs]
            labels = [lbl for _, lbl in _pairs]
            ax.set_xticks(positions)
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=_fs)

        mpl_hooks.append(_mpl_xticks_hook)
        overlay_opts.append(hv.opts.Overlay(backend="bokeh", xticks=xticks_pairs, xrotation=30))
    overlay_opts.append(
        hv.opts.Overlay(backend="matplotlib", fig_inches=fig_inches, hooks=mpl_hooks)
    )
    return overlay.opts(*overlay_opts)


def render_regression_png(
    result: RegressionResult,
    historical: np.ndarray | None = None,
    current: np.ndarray | float | None = None,
    path: str | Path | None = None,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 100,
) -> str:
    """Render a diagnostic PNG by saving the shared holoviews overlay via matplotlib.

    Produces the same plot as the in-report bokeh overlay — it calls
    :func:`build_regression_overlay` and hands the result to holoviews'
    matplotlib renderer, so there's a single source of truth for the
    diagnostic visual.

    Args:
        result: The :class:`RegressionResult` produced by a ``detect_*`` call.
        historical: 1-D array of historical per-time-point means. Falls back
            to ``result.historical``.
        current: Current-run sample(s). Falls back to ``result.current_samples``
            / ``result.current_value``.
        path: Output PNG path. If ``None``, a path is generated via
            :func:`bencher.utils.gen_image_path` so the file lives under the
            bencher cache directory.
        figsize: Figure size in inches (matplotlib ``fig_inches``).
        dpi: Output DPI (500x320 at ``dpi=100`` works well for GitHub comments).

    Returns:
        Absolute path to the saved PNG as a string.
    """
    import holoviews as hv

    if path is None:
        from bencher.utils import gen_image_path

        path = gen_image_path(f"regression_{result.variable}")
    path_str = str(path)

    _ensure_matplotlib_backend_loaded()
    overlay = build_regression_overlay(
        result, historical=historical, current=current, fig_inches=figsize
    )
    # hv.renderer(...).save re-tightens the bbox and collapses the figure to
    # roughly square regardless of fig_inches. Rendering to a Figure and
    # using matplotlib's own savefig preserves the requested inches.
    import matplotlib.pyplot as plt

    fig = hv.render(overlay, backend="matplotlib")
    fig.savefig(path_str, dpi=dpi)
    plt.close(fig)
    return path_str


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
    regression_mad: float = 3.5,
    drift_threshold: float | None = None,
    mk_alpha: float = 0.1,
    direction: OptDir = OptDir.minimize,
    historical_samples: np.ndarray | None = None,
    regression_percentage: float | None = None,
) -> RegressionResult:
    """Robust regression detection combining step and drift tests.

    The method estimates the metric's inherent noise from history using a
    median + MAD (median absolute deviation) scale and expresses the current
    run's deviation in those noise units. Two orthogonal tests run in parallel:

    * **Short-term step** — flags if ``(current_mean - baseline) / noise_floor``
      exceeds ``regression_mad`` in the regression direction.
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
        regression_mad: Step-test threshold in MAD-sigma units.
        drift_threshold: Drift-test threshold in MAD-sigma units. If ``None``,
            defaults to ``_DRIFT_FRAC * regression_mad`` so users need to tune
            only one knob.
        mk_alpha: Significance level for the Mann–Kendall trend guard.
        direction: Optimization direction from the result variable.
        historical_samples: Optional flat array of all historical samples
            (not per-time means). Used for the sparse-history fallback so the
            delegated ``percentage`` detector sees the same input it would
            have received from ``detect_regressions`` directly. Falls back to
            ``historical_time_means`` when not provided.
        regression_percentage: Optional minimum percent change required to
            flag a regression (directional, i.e. interpreted against
            ``direction``). When set, acts as a second acceptance band: a
            regression fires only when BOTH the MAD test and the percent
            change exceed their thresholds. Suppresses noise-floor false
            positives on metrics with few repeats or very tight history.
    """
    if drift_threshold is None:
        drift_threshold = _DRIFT_FRAC * regression_mad

    hist_clean = _clean_1d(historical_time_means)
    curr_clean = _clean_1d(current)
    curr_mean = float(np.mean(curr_clean)) if len(curr_clean) else float("nan")

    # Not enough history for a robust scale — fall back to a percentage
    # check. Use the full per-sample history when available so the fallback
    # behaves like a direct call to detect_percentage.
    if len(hist_clean) < 4:
        fallback_hist = (
            _clean_1d(historical_samples) if historical_samples is not None else hist_clean
        )
        # Sparse history -> percentage check. When ``regression_percentage`` is
        # set it doubles as the percentage threshold so the sparse regime honours
        # the same knob the user configured for dual-band suppression.
        effective_pct = (
            regression_percentage
            if regression_percentage is not None
            else _METHOD_DEFAULTS["percentage"]
        )
        result = detect_percentage(
            variable,
            fallback_hist,
            curr_clean,
            threshold_percent=effective_pct,
            direction=direction,
        )
        if regression_percentage is not None:
            baseline = result.baseline_value
            result.percent_band_lower = baseline * (1.0 - regression_percentage / 100.0)
            result.percent_band_upper = baseline * (1.0 + regression_percentage / 100.0)
        return result

    baseline, mad_sigma = _robust_scale(hist_clean)
    noise_floor = max(mad_sigma, 1e-6 * abs(baseline), 1e-12)

    # Step test — current mean vs robust baseline in MAD-sigma units.
    z_step = (curr_mean - baseline) / noise_floor
    step_mad = _is_regression(z_step, direction) and abs(z_step) > regression_mad

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
    drift_mad = (
        _is_regression(z_drift, direction) and abs(z_drift) > drift_threshold and mk_p < mk_alpha
    )

    change = _safe_change_percent(curr_mean, baseline)

    # Dual-band gate: when regression_percentage is set, each test must also
    # be confirmed by a percent-change gate. The step gate uses the observed
    # current-vs-baseline change; the drift gate uses the projected end-of-
    # history drift so a trend that doesn't cumulatively move more than the
    # threshold is treated as inside the band.
    if regression_percentage is not None:
        step_pct_ok = _exceeds_directional_threshold(change, regression_percentage, direction)
        drift_change = _safe_change_percent(baseline + drift_total, baseline)
        drift_pct_ok = _exceeds_directional_threshold(
            drift_change, regression_percentage, direction
        )
        percent_band_lower = baseline * (1.0 - regression_percentage / 100.0)
        percent_band_upper = baseline * (1.0 + regression_percentage / 100.0)
    else:
        step_pct_ok = True
        drift_pct_ok = True
        percent_band_lower = None
        percent_band_upper = None

    step_regressed = step_mad and step_pct_ok
    drift_regressed = drift_mad and drift_pct_ok
    regressed = step_regressed or drift_regressed

    fired = []
    if step_regressed:
        fired.append("step")
    if drift_regressed:
        fired.append("drift")
    fired_str = "+".join(fired) if fired else "none"
    details = (
        f"fired={fired_str}, z_step={z_step:+.2f} (|z|>{regression_mad}), "
        f"z_drift={z_drift:+.2f} (|z|>{drift_threshold:.2f}), "
        f"mk_p={mk_p:.3g} (<{mk_alpha}), "
        f"baseline={baseline:.4g}, noise={noise_floor:.4g}"
    )
    if regression_percentage is not None:
        details += f", pct={regression_percentage}% (change={change:+.2f}%)"

    return RegressionResult(
        variable=variable,
        method="adaptive",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=baseline,
        change_percent=change,
        threshold=regression_mad,
        direction=direction.value,
        details=details,
        band_lower=baseline - regression_mad * noise_floor,
        band_upper=baseline + regression_mad * noise_floor,
        percent_band_lower=percent_band_lower,
        percent_band_upper=percent_band_upper,
    )


def detect_delta(
    variable: str,
    historical_time_means: np.ndarray,
    current: np.ndarray,
    max_delta: float,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Fail when the current mean's delta from history exceeds ``max_delta``.

    The comparison respects ``direction``: ``minimize`` fails when
    ``curr - hist_mean > max_delta``; ``maximize`` fails when
    ``hist_mean - curr > max_delta``; ``none`` uses the absolute delta and fails
    on either side. Baseline is the mean of all historical per-time means, so
    this compares the current scalar against a flat historical average in
    absolute units (not percent). Intended as an additive guard alongside the
    statistical methods.
    """
    hist_clean = _clean_1d(historical_time_means)
    hist_mean = float(np.nanmean(hist_clean)) if len(hist_clean) else float("nan")
    curr_clean = _clean_1d(current)
    curr_mean = float(np.mean(curr_clean)) if len(curr_clean) else float("nan")
    delta = curr_mean - hist_mean

    if direction == OptDir.minimize:
        regressed = delta > max_delta
    elif direction == OptDir.maximize:
        regressed = delta < -max_delta
    else:
        regressed = abs(delta) > max_delta

    return RegressionResult(
        variable=variable,
        method="delta",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=hist_mean,
        change_percent=_safe_change_percent(curr_mean, hist_mean),
        threshold=max_delta,
        direction=direction.value,
        details=f"delta={delta:+.4g} vs max |{max_delta}|",
        band_lower=hist_mean - max_delta,
        band_upper=hist_mean + max_delta,
    )


def detect_absolute(
    variable: str,
    current: np.ndarray,
    limit: float,
    direction: OptDir = OptDir.minimize,
) -> RegressionResult:
    """Fail when current mean violates an absolute limit in the direction of OptDir.

    Needs no historical data. For ``OptDir.minimize`` ``limit`` is a ceiling;
    for ``OptDir.maximize`` it's a floor. ``OptDir.none`` has no direction so
    the guard records a non-regressed result and leaves it to the caller to log.
    """
    curr_clean = _clean_1d(current)
    curr_mean = float(np.mean(curr_clean)) if len(curr_clean) else float("nan")

    if direction == OptDir.minimize:
        regressed = curr_mean > limit
        detail = f"current={curr_mean:.4g} vs ceiling {limit}"
    elif direction == OptDir.maximize:
        regressed = curr_mean < limit
        detail = f"current={curr_mean:.4g} vs floor {limit}"
    else:
        regressed = False
        detail = f"OptDir.none: absolute guard skipped (current={curr_mean:.4g})"

    return RegressionResult(
        variable=variable,
        method="absolute",
        regressed=regressed,
        current_value=curr_mean,
        baseline_value=float(limit),
        change_percent=float("nan"),
        threshold=float(limit),
        direction=direction.value,
        details=detail,
    )


def _compute_history_arrays(
    da: xr.DataArray,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    """Aggregate history into per-time means + per-sample scatter arrays.

    Returns ``(time_means, hist_samples_flat, hist_x_flat)`` or all-``None``
    when there is no history to summarise. Per-time means collapse every
    non-time dim into one scalar per run so detection and plotting both see
    a 1-D series; the scatter arrays preserve per-repeat spread broadcast
    against the historical over_time coords.
    """
    if da.sizes.get("over_time", 0) < 2:
        return None, None, None

    reduce_dims = [d for d in da.dims if d != "over_time"]
    time_means = (
        da.isel(over_time=slice(None, -1)).mean(dim=reduce_dims, skipna=True).values.astype(float)
    )

    hist_slice = da.isel(over_time=slice(None, -1))
    if hist_slice.size == 0:
        return time_means, None, None

    hist_2d = np.moveaxis(
        np.asarray(hist_slice.values, dtype=float),
        list(hist_slice.dims).index("over_time"),
        0,
    ).reshape(hist_slice.sizes["over_time"], -1)
    hist_samples_flat = hist_2d.ravel()
    hist_x_flat = np.repeat(da["over_time"].values[:-1], hist_2d.shape[1])
    return time_means, hist_samples_flat, hist_x_flat


def _attach_plot_metadata(
    result: RegressionResult,
    *,
    time_coord: np.ndarray,
    current_samples: np.ndarray,
    time_means: np.ndarray | None,
    hist_samples_flat: np.ndarray | None,
    hist_x_flat: np.ndarray | None,
) -> None:
    """Attach the history/current arrays a RegressionResult needs for replay plotting."""
    result.current_x = time_coord[-1]
    result.current_samples = current_samples
    if time_means is not None:
        result.historical = time_means
        result.historical_x = time_coord[:-1]
    if hist_samples_flat is not None and hist_x_flat is not None:
        mask = ~np.isnan(hist_samples_flat)
        result.historical_all = hist_samples_flat[mask]
        result.historical_all_x = hist_x_flat[mask]


def detect_regressions(dataset: xr.Dataset, bench_cfg, run_cfg) -> RegressionReport:
    """Run regression detection on a dataset with over_time dimension.

    For each numeric result variable, splits the dataset at the last over_time
    index, runs the configured statistical method (percentage/adaptive), and
    layers the optional additive guards (regression_delta, regression_absolute)
    on top. regression_absolute runs even with a single over_time point since
    it needs no baseline.

    Args:
        dataset: xarray Dataset with an over_time dimension.
        bench_cfg: BenchCfg with ``result_vars`` list.
        run_cfg: BenchRunCfg. Reads ``regression_method``, ``regression_mad``,
            ``regression_percentage``, ``regression_delta`` and
            ``regression_absolute``.

    Returns:
        RegressionReport with one result per variable per fired detector/guard.
    """
    report = RegressionReport()

    if "over_time" not in dataset.dims:
        return report

    n_times = dataset.sizes["over_time"]
    regression_absolute = getattr(run_cfg, "regression_absolute", None)
    regression_delta = getattr(run_cfg, "regression_delta", None)

    # With no history, only the absolute guard has anything to compare against.
    if n_times < 2 and regression_absolute is None:
        return report

    method = run_cfg.regression_method
    regression_mad = getattr(run_cfg, "regression_mad", None)
    if regression_mad is None:
        regression_mad = _METHOD_DEFAULTS["adaptive"]
    regression_percentage = getattr(run_cfg, "regression_percentage", None)
    if regression_percentage is None:
        regression_percentage = _METHOD_DEFAULTS["percentage"]

    time_coord = dataset["over_time"].values

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

        if len(current_clean) == 0:
            continue

        current_mean_scalar = np.array([float(da.isel(over_time=-1).mean(skipna=True).values)])
        time_means_arr, hist_samples_flat, hist_x_flat = _compute_history_arrays(da)
        history_available = time_means_arr is not None and len(historical_clean) > 0

        if history_available:
            if method == "percentage":
                result = detect_percentage(
                    var_name,
                    time_means_arr,
                    current_mean_scalar,
                    regression_percentage,
                    direction,
                )
            elif method == "adaptive":
                result = detect_adaptive(
                    var_name,
                    time_means_arr,
                    current_mean_scalar,
                    regression_mad=regression_mad,
                    direction=direction,
                    historical_samples=historical_clean,
                    regression_percentage=regression_percentage,
                )
            else:
                logging.warning(f"Unknown regression method '{method}', falling back to percentage")
                result = detect_percentage(
                    var_name,
                    time_means_arr,
                    current_mean_scalar,
                    regression_percentage,
                    direction,
                )
            _attach_plot_metadata(
                result,
                time_coord=time_coord,
                current_samples=current_clean,
                time_means=time_means_arr,
                hist_samples_flat=hist_samples_flat,
                hist_x_flat=hist_x_flat,
            )
            report.results.append(result)

        # Additive guards — run independently of the statistical method.
        if regression_delta is not None and history_available:
            delta_result = detect_delta(
                var_name,
                time_means_arr,
                current_mean_scalar,
                max_delta=regression_delta,
                direction=direction,
            )
            _attach_plot_metadata(
                delta_result,
                time_coord=time_coord,
                current_samples=current_clean,
                time_means=time_means_arr,
                hist_samples_flat=hist_samples_flat,
                hist_x_flat=hist_x_flat,
            )
            report.results.append(delta_result)

        if regression_absolute is not None:
            if direction == OptDir.none:
                logging.warning(
                    f"regression_absolute skipped for '{var_name}': OptDir.none has no direction"
                )
            else:
                abs_result = detect_absolute(
                    var_name,
                    current_mean_scalar,
                    limit=regression_absolute,
                    direction=direction,
                )
                _attach_plot_metadata(
                    abs_result,
                    time_coord=time_coord,
                    current_samples=current_clean,
                    time_means=None,
                    hist_samples_flat=None,
                    hist_x_flat=None,
                )
                report.results.append(abs_result)

    return report
