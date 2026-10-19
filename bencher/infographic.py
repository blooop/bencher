"""The evidence graphics G1–G9 of ``docs/statistical_evidence.md`` §5, as matplotlib Figures.

Each ``draw_*`` function takes the :class:`~bencher.evidence_stats.MetricEvidence`
records it shows and a :class:`Theme` and returns a ``matplotlib.figure.Figure``
built without pyplot (no global backend state, safe in any process).
:func:`save_both` draws one graphic in the light and the dark theme and writes
each as a PNG at 2× (1600 px wide, shown at 800) and as an SVG.

The rules every graphic keeps:

* Okabe–Ito colours: base grey, candidate blue; better bluish green, worse
  vermillion, inconclusive amber. A glyph and a word always back a colour, and
  text wears the theme's ink, never a data colour.
* One effect axis: % change on a log-ratio scale (or percentage points for a
  binary metric), 0 in the middle, the ±Δ margin band shaded.
* The title is the finding ("Planning time is 18 % faster"), not the axes.
* The 90 % CI (the decision) is drawn thick, the 95 % CI thin; a mark whose
  metric fails the FDR check is hollow.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from bencher.evidence_stats import (
    Effect,
    MetricEvidence,
    ProportionEffect,
    ShiftFunction,
    VerdictKind,
    quantile_ci,
    shift_function,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from matplotlib.axes import Axes
    from matplotlib.figure import Figure, FigureBase, SubFigure

WIDTH_IN = 8.0
DPI = 200
"""8 in at 200 dpi is 1600 px: a 2× image for an 800 px wide PR body."""
FONT = ("Open Sans", "DejaVu Sans")
"""Open Sans where it is installed; DejaVu Sans (always there) supplies ▲ ▼ ≈ and the fallback."""


@dataclass(frozen=True)
class Theme:
    """Colours of one theme. Data colours are the spec's Okabe–Ito set in both themes."""

    name: str
    surface: str
    tile: str
    ink: str
    ink2: str
    muted: str
    grid: str
    band: str
    mid: str
    base: str = "#8C8C8C"
    cand: str = "#0072B2"
    better: str = "#009E73"
    worse: str = "#D55E00"
    unsure: str = "#E69F00"

    def verdict_colour(self, kind: VerdictKind) -> str:
        return {
            VerdictKind.IMPROVED: self.better,
            VerdictKind.REGRESSED: self.worse,
            VerdictKind.EQUIVALENT: self.ink2,
            VerdictKind.INCONCLUSIVE: self.unsure,
        }[kind]


LIGHT = Theme(
    name="light",
    surface="#ffffff",
    tile="#f6f8fa",
    ink="#1f2328",
    ink2="#59636e",
    muted="#818b98",
    grid="#e3e8ee",
    band="#dfe6ee",
    mid="#f2f2f2",
)
DARK = Theme(
    name="dark",
    surface="#0d1117",
    tile="#161b22",
    ink="#f0f6fc",
    ink2="#b0b8c1",
    muted="#8b949e",
    grid="#262c34",
    band="#253142",
    mid="#2a3038",
    # Okabe–Ito lifted for the dark surface (validated): each clears 3:1 on #0d1117.
    cand="#3D9BD6",
    better="#1FA07C",
    worse="#E0662A",
    unsure="#BE8714",
)
THEMES = (LIGHT, DARK)

# Type scale (pt). At 8 in shown 800 px wide, 1 pt is ~1.4 px on screen.
_TITLE = 15
_SUB = 10
_BODY = 9.5
_SMALL = 8.5
_HERO = 27

_ZERO = 1e-9
_DENSITY_FLOOR = 0.01  # below this the KDE outline is not drawn (no hairline at 0)


# --------------------------------------------------------------------------------------
# Words and numbers.


def humanize(name: str) -> str:
    """``planning_time`` -> ``Planning time``."""
    text = name.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


_TIME_UNITS = {"s", "sec", "secs", "seconds", "ms", "us", "µs", "ns", "min", "minutes", "h"}


def display(m: MetricEvidence, value: float) -> float:
    """An effect-scale value in the unit the report prints: %, pp, or the metric's units."""
    if m.kind == "positive":
        return 100.0 * math.expm1(value)
    if m.kind in ("binary", "fraction"):
        return 100.0 * value
    return value


def unit_suffix(m: MetricEvidence) -> str:
    if m.kind == "positive":
        return " %"
    if m.kind in ("binary", "fraction"):
        return " pp"
    return f" {m.units}" if m.units else ""


def fmt_signed(value: float, digits: int = 1) -> str:
    """``-18.4`` -> ``−18.4`` with a true minus; ``+`` on positives; 0 has no sign."""
    text = f"{abs(value):.{digits}f}"
    if float(text) == 0:
        return text
    return ("−" if value < 0 else "+") + text


def fmt_effect(m: MetricEvidence) -> str:
    """The headline number: ``−18.4 %``, ``+5.6 pp`` or ``+0.12 m``."""
    return fmt_signed(display(m, m.effect.estimate), _digits(m)) + unit_suffix(m)


def fmt_ci(m: MetricEvidence, *, level95: bool = False) -> str:
    ci = m.effect.ci95 if level95 else m.effect.ci
    d = _digits(m)
    lo, hi = fmt_signed(display(m, ci.low), d), fmt_signed(display(m, ci.high), d)
    return f"{round(ci.level * 100):d} % CI {lo} … {hi}{unit_suffix(m)}"


def fmt_margin(m: MetricEvidence) -> str:
    if m.kind == "positive":
        return f"±{100 * m.margin:g} %"
    if m.kind in ("binary", "fraction"):
        return f"±{100 * m.margin:g} pp"
    return f"±{m.margin:.3g}{unit_suffix(m)}"


def _digits(m: MetricEvidence) -> int:
    if m.kind == "signed":
        span = abs(m.effect.ci95.high - m.effect.ci95.low)
        return max(0, min(4, 2 - math.floor(math.log10(span)))) if span > 0 else 2
    return 1


def fmt_counts(effect: ProportionEffect) -> str:
    return f"{effect.k_base}/{effect.n_base} → {effect.k_cand}/{effect.n_cand}"


def _direction_word(m: MetricEvidence, raised: bool) -> str:
    if m.units.strip().lower() in _TIME_UNITS or "time" in m.name or "duration" in m.name:
        return "slower" if raised else "faster"
    return "higher" if raised else "lower"


def headline(m: MetricEvidence) -> str:
    """The finding as a chart title: "Planning time is 18 % faster"."""
    name = humanize(m.name)
    v = m.verdict
    if isinstance(m.effect, ProportionEffect):
        e = m.effect
        moved = f"{fmt_counts(e)} ({fmt_signed(100 * e.estimate)} pp)"
        if v.kind == VerdictKind.EQUIVALENT and v.detail == "no change":
            return f"{name} unchanged within {fmt_margin(m)}: {moved}"
        if v.kind == VerdictKind.INCONCLUSIVE:
            return f"{name}: not yet known, {moved}"
        return f"{name} {v.word}: {moved}"
    size = display(m, m.effect.estimate)
    raised = m.effect.estimate > 0
    if m.kind == "positive":
        amount = f"{abs(size):.0f} %" if abs(size) >= 10 else f"{abs(size):.1f} %"  # noqa: PLR2004
    else:
        amount = f"{abs(size):.{_digits(m)}f}{unit_suffix(m)}"
    if v.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED):
        return f"{name} is {amount} {_direction_word(m, raised)}"
    if v.kind == VerdictKind.EQUIVALENT:
        if v.detail == "no change":
            return f"{name} is unchanged within {fmt_margin(m)}"
        return f"{name} is {amount} {_direction_word(m, raised)}, inside {fmt_margin(m)}"
    return f"{name}: not yet known ({fmt_effect(m)}, {fmt_ci(m)})"


def method_line(m: MetricEvidence) -> str:
    """The tile footer: ``n=20 paired · BCa · MDE 4.1 %``."""
    e = m.effect
    if isinstance(e, ProportionEffect):
        n = f"n={e.n_base}/{e.n_cand}" + (" paired" if e.paired else "")
        test = "McNemar" if e.paired else e.method.split("· ")[-1].split(" (")[0]
        parts = [n, "Newcombe", test]
    else:
        if e.paired:
            n = f"n={e.n_base} paired"
        elif e.n_base == e.n_cand:
            n = f"n={e.n_base} per arm"
        else:
            n = f"n={e.n_base}/{e.n_cand}"
        if e.n_clusters:
            n += f" · {e.n_clusters} shards"
        parts = [n, "BCa" if e.bootstrap is not None else "Welch t"]
    if m.verdict.mde is not None:
        mde = display(m, m.verdict.mde) if m.kind != "positive" else 100 * math.expm1(m.verdict.mde)
        parts.append(f"MDE {abs(mde):.1f}{unit_suffix(m)}")
    return " · ".join(parts)


def verdict_label(m: MetricEvidence) -> str:
    """``▲ improved``, ``≈ no change``, ``? inconclusive``."""
    return f"{m.verdict.glyph} {m.verdict.word}"


def alt_text(m: MetricEvidence) -> str:
    """One sentence a screen reader (or a broken image) still gets the result from."""
    if isinstance(m.effect, ProportionEffect):
        nums = f"{fmt_counts(m.effect)}, difference {fmt_effect(m)} ({fmt_ci(m)})"
    else:
        nums = f"{fmt_effect(m)} ({fmt_ci(m)})"
    extra = " Underpowered." if m.verdict.underpowered else ""
    return f"{humanize(m.name)}: {m.verdict.word}, {nums}, margin {fmt_margin(m)}.{extra}"


# --------------------------------------------------------------------------------------
# Drawing helpers.


def _figure(height_in: float, theme: Theme) -> Figure:
    from matplotlib.figure import Figure

    fig = Figure(figsize=(WIDTH_IN, height_in), dpi=DPI, facecolor=theme.surface)
    fig.set_layout_engine("none")
    return fig


def _figure_with_strip(
    height_in: float, theme: Theme, strip_in: float = 0.0
) -> tuple[Figure, FigureBase, SubFigure | None]:
    """A root figure, the subfigure the graphic draws in, and the design strip under it.

    The graphic's code lays itself out in fractions of *height_in*, as if it had
    the whole figure; the strip adds *strip_in* inches below it.
    """
    root = _figure(height_in + strip_in, theme)
    if strip_in <= 0:
        return root, root, None
    subs = np.asarray(
        root.subfigures(2, 1, height_ratios=[height_in, strip_in], hspace=0), dtype=object
    ).ravel()
    main, strip = subs[0], subs[1]
    for sub in (main, strip):
        sub.set_facecolor(theme.surface)
    return root, main, strip


def _rc() -> dict:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": list(FONT),
        "svg.fonttype": "path",
        "axes.unicode_minus": True,
    }


def _title(fig: Figure, title: str, subtitle: str | None, theme: Theme, height_in: float) -> None:
    top = 1.0 - 0.28 / height_in
    fig.text(0.04, top, title, ha="left", va="top", fontsize=_TITLE, weight="bold", color=theme.ink)
    if subtitle:
        fig.text(
            0.04,
            top - 0.34 / height_in,
            subtitle,
            ha="left",
            va="top",
            fontsize=_SUB,
            color=theme.ink2,
        )


def _axes(fig: FigureBase, rect: Sequence[float], theme: Theme) -> Axes:
    ax = fig.add_axes((rect[0], rect[1], rect[2], rect[3]))
    ax.set_facecolor(theme.surface)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme.grid)
    ax.tick_params(colors=theme.ink2, labelsize=_SMALL, length=0, pad=4)
    ax.grid(visible=False)
    return ax


def _hgrid(ax: Axes, theme: Theme) -> None:
    ax.grid(axis="y", color=theme.grid, linewidth=0.8)
    ax.set_axisbelow(True)


def _nice_step(span: float) -> float:
    """A 1/2/2.5/5 × 10^k tick step that puts at least three ticks across *span*."""
    raw = span / 5.0
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def effect_limits(metrics: Sequence[MetricEvidence], pad: float = 0.12) -> tuple[float, float]:
    """Symmetric effect-axis limits that hold every 95 % CI and every margin."""
    reach = 0.0
    for m in metrics:
        delta = math.log1p(m.margin) if m.kind == "positive" else m.margin
        reach = max(reach, abs(m.effect.ci95.low), abs(m.effect.ci95.high), delta)
    reach = reach * (1 + pad) if reach > 0 else 0.1
    return -reach, reach


def _effect_axis(
    ax: Axes,
    m: MetricEvidence,
    lim: tuple[float, float],
    theme: Theme,
    *,
    vertical: bool = False,
    ticks: bool = True,
) -> None:
    """Draw the shared effect axis: limits, % ticks, the 0 line and the ±Δ band."""
    delta = _delta(m)
    span_fn = ax.axhspan if vertical else ax.axvspan
    line_fn = ax.axhline if vertical else ax.axvline
    span_fn(-delta, delta, color=theme.band, zorder=0, linewidth=0)
    line_fn(0, color=theme.muted, linewidth=0.9, zorder=1)
    (ax.set_ylim if vertical else ax.set_xlim)(*lim)
    if not ticks:
        (ax.set_yticks if vertical else ax.set_xticks)([])
        return
    if m.kind == "positive":
        lo_p, hi_p = 100 * math.expm1(lim[0]), 100 * math.expm1(lim[1])
    else:
        lo_p, hi_p = display(m, lim[0]), display(m, lim[1])
    step = _nice_step(hi_p - lo_p)
    vals = np.arange(math.ceil(lo_p / step) * step, hi_p + 1e-9, step)
    pos = np.log1p(vals / 100.0) if m.kind == "positive" else vals / (display(m, 1.0) or 1.0)
    unit = unit_suffix(m)
    labels = [_tick(v, step) + ("" if abs(v) < _ZERO else unit) for v in vals]
    (ax.set_yticks if vertical else ax.set_xticks)(pos, labels)


def _tick(value: float, step: float) -> str:
    digits = 0 if step >= 1 else max(0, -math.floor(math.log10(step)))
    if abs(value) < _ZERO:
        return "0"
    return fmt_signed(value, digits)


def _ci_marks(
    ax: Axes,
    pos: float,
    effect: Effect | ProportionEffect,
    colour: str,
    theme: Theme,
    *,
    vertical: bool = False,
    hollow: bool = False,
    size: float = 8.0,
) -> None:
    """Point + thick 90 % CI + thin 95 % CI at row/column *pos*."""
    lw95, lw90 = 1.4, 4.6
    if vertical:
        ax.plot(
            [pos, pos],
            [effect.ci95.low, effect.ci95.high],
            color=colour,
            lw=lw95,
            solid_capstyle="round",
            zorder=3,
        )
        ax.plot(
            [pos, pos],
            [effect.ci.low, effect.ci.high],
            color=colour,
            lw=lw90,
            solid_capstyle="round",
            zorder=3,
        )
        xy = ([pos], [effect.estimate])
    else:
        ax.plot(
            [effect.ci95.low, effect.ci95.high],
            [pos, pos],
            color=colour,
            lw=lw95,
            solid_capstyle="round",
            zorder=3,
        )
        ax.plot(
            [effect.ci.low, effect.ci.high],
            [pos, pos],
            color=colour,
            lw=lw90,
            solid_capstyle="round",
            zorder=3,
        )
        xy = ([effect.estimate], [pos])
    ax.plot(
        *xy,
        marker="o",
        markersize=size,
        markerfacecolor=theme.surface if hollow else colour,
        markeredgecolor=colour if hollow else theme.surface,
        markeredgewidth=1.8,
        linestyle="",
        zorder=4,
    )


def _glyph_marker(kind: VerdictKind) -> str:
    return {
        VerdictKind.IMPROVED: "^",
        VerdictKind.REGRESSED: "v",
        VerdictKind.EQUIVALENT: "D",
        VerdictKind.INCONCLUSIVE: "o",
    }[kind]


def _kde(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Gaussian kernel density with Scott's bandwidth (numpy only)."""
    v = values[np.isfinite(values)]
    sd = v.std(ddof=1) if len(v) > 1 else 0.0
    iqr = np.subtract(*np.percentile(v, [75, 25])) / 1.349 if len(v) > 1 else 0.0
    spread = min(sd, iqr) if iqr > 0 else sd
    bw = 1.06 * (spread if spread > 0 else max(abs(v.mean()) * 0.01, 1e-9)) * len(v) ** -0.2
    z = (grid[:, None] - v[None, :]) / bw
    return np.exp(-0.5 * z * z).sum(axis=1) / (len(v) * bw * math.sqrt(2 * math.pi))


def _swarm(
    values: np.ndarray, half_width: float, span: float, marker_frac: float = 0.03
) -> np.ndarray:
    """Horizontal offsets that keep points of similar value apart (a simple beeswarm)."""
    order = np.argsort(values)
    offsets = np.zeros(len(values))
    bin_size = span * marker_frac if span > 0 else 1.0
    placed: list[tuple[float, float]] = []
    step = half_width / 6.0
    for i in order:
        y = values[i]
        k = 0
        while True:
            off = (k + 1) // 2 * step * (1 if k % 2 else -1)
            if all(abs(y - py) >= bin_size or abs(off - px) >= step * 0.95 for py, px in placed):
                break
            k += 1
            if abs(off) > half_width:
                off = float(np.clip(off, -half_width, half_width))
                break
        offsets[i] = off
        placed.append((y, off))
    return offsets


def _chip(
    ax: Axes, x: float, y: float, m: MetricEvidence, theme: Theme, *, size: float = _BODY
) -> None:
    """The verdict as a coloured glyph followed by the word in ink, at axes position (x, y)."""
    colour = theme.verdict_colour(m.verdict.kind)
    word = m.verdict.word
    if m.verdict.underpowered and m.verdict.kind == VerdictKind.INCONCLUSIVE:
        word += " · underpowered"
    g = ax.text(
        x,
        y,
        m.verdict.glyph,
        ha="left",
        va="center",
        fontsize=size,
        color=colour,
        weight="bold",
        transform=ax.transAxes,
    )
    ax.annotate(
        " " + word, xy=(1, 0.5), xycoords=g, ha="left", va="center", fontsize=size, color=theme.ink
    )


# --------------------------------------------------------------------------------------
# The design strip: how the run was made, drawn into the graphic itself.

_SQUARE_MAX_IN = 0.11


@dataclass(frozen=True)
class SweepGrid:
    """The swept grid for the strip's dot matrix: every point, and the ones that were run."""

    xs: tuple
    ys: tuple | None
    run: frozenset
    x_name: str = "x"
    y_name: str = "y"


@dataclass(frozen=True)
class _Run:
    order: float | None
    arm: int  # 0 base, 1 candidate
    shard: str | None


def _runs(cells: Sequence[MetricEvidence]) -> list[_Run]:
    """Every run behind *cells*: one per sample per arm (one metric's samples stand for all)."""
    out = []
    for m in cells:
        for arm, vals in ((0, m.base), (1, m.cand)):
            order = m.order[arm]
            shards = m.clusters[0] if m.paired else m.clusters[arm]
            out.extend(
                _Run(
                    None if order is None else float(order[i]),
                    arm,
                    None if shards is None else str(shards[i]),
                )
                for i in range(len(vals))
            )
    return out


def _order_pattern(runs: Sequence[_Run]) -> str:
    """``blocked``, ``interleaved``, ``ABBA`` or ``mixed`` from the arm sequence in run order."""
    seq = [r.arm for r in sorted(runs, key=lambda r: r.order or 0.0)]
    switches = sum(a != b for a, b in itertools.pairwise(seq))
    if switches <= 1:
        return "blocked"
    if switches >= len(seq) - 1:
        return "interleaved"
    pairs = [tuple(seq[i : i + 2]) for i in range(0, len(seq) - 1, 2)]
    if all(len(set(p)) == 2 for p in pairs):  # noqa: PLR2004
        return "ABBA" if len(set(pairs)) == 2 else "paired, same order"  # noqa: PLR2004
    return "mixed"


def test_label(m: MetricEvidence) -> str:
    """``BCa bootstrap of paired log diffs, 90 % CI, Holm ×3``."""
    e = m.effect
    if isinstance(e, ProportionEffect):
        test = "Newcombe CI, " + e.method.split("· ")[-1].split(" (")[0]
    elif e.bootstrap is not None:
        what = "log diffs" if m.kind == "positive" else "diffs"
        test = f"BCa bootstrap of {'paired ' if e.paired else ''}{what if e.paired else 'log ratio' if m.kind == 'positive' else 'difference'}"
        if e.n_clusters:
            test += " by shard"
    else:
        test = "paired t" if e.paired else "Welch t" + (" on logs" if m.kind == "positive" else "")
    test += f", {round(100 * e.ci.level)} % CI"
    if m.primary and m.holm_m > 1:
        test += f", Holm ×{m.holm_m}"
    elif not m.primary:
        test += ", BH q 0.05"
    return test


def design_facts(cells: Sequence[MetricEvidence], *, points: int = 1) -> list[tuple[str, str]]:
    """The labelled facts of the strip's chips, from the first cell (and the cell count)."""
    m = cells[0]
    e = m.effect
    shards = {r.shard for r in _runs([m]) if r.shard is not None}
    if shards:
        design = f"{'paired, ' if m.paired else ''}clustered by shard ({len(shards)})"
    else:
        design = "paired" if m.paired else "unpaired"
    n = f"{e.n_base} pairs" if m.paired else f"{e.n_base} / {e.n_cand} per arm"
    reps = max(e.n_base, e.n_cand)
    return [
        ("design", design),
        ("n", n),
        ("runs", f"{reps} repeats × {points} point{'s' if points != 1 else ''}"),
        ("seeds", m.seed_policy or "not recorded"),
        ("margin", f"{fmt_margin(m)}, set before the run"),
        ("test", test_label(m)),
    ]


def _text_w_in(text: str, size: float) -> float:
    # DejaVu/Open Sans average advance is ~0.55 em; enough to flow chips without a renderer.
    return len(text) * size * 0.56 / 72.0


_SQUARE_MIN_IN = 0.06


def _schematic_rows(
    runs: Sequence[_Run], width_in: float
) -> tuple[list[tuple[str | None, list[_Run]]], float]:
    """The schematic's lines (a shard's runs wrap onto more lines when too many) and its label width."""
    recorded = all(r.order is not None for r in runs)
    shards = sorted({r.shard for r in runs}, key=str) if any(r.shard for r in runs) else [None]
    label_w = 0.42 if shards != [None] else 0.0
    per_line = max(1, int((width_in - label_w) / _SQUARE_MIN_IN))
    lines: list[tuple[str | None, list[_Run]]] = []
    for s in shards:
        mine = sorted(
            (r for r in runs if r.shard == s), key=lambda r: (r.order if recorded else r.arm) or 0.0
        )
        lines.extend(
            (s if k == 0 else None, mine[k : k + per_line]) for k in range(0, len(mine), per_line)
        )
    return lines, label_w


def _draw_schematic(
    ax: Axes, runs: Sequence[_Run], theme: Theme, width_in: float, height_in: float
) -> None:
    """One square per run in execution order, base grey / candidate blue, one row per shard."""
    ax.set_axis_off()
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, height_in)
    recorded = all(r.order is not None for r in runs)
    lines, label_w = _schematic_rows(runs, width_in)
    longest = max(len(v) for _, v in lines)
    pitch = min(_SQUARE_MAX_IN, (height_in - 0.26) / len(lines))
    sq = min(pitch, (width_in - label_w) / max(longest, 1))
    gap = sq * 0.18
    head = "run order →" if recorded else "order not recorded (grouped by arm)"
    if recorded:
        head += f"   {_order_pattern(runs)}"
    ax.text(0, height_in - 0.02, head, fontsize=_SMALL - 0.5, color=theme.muted, va="top")
    for j, (s, line) in enumerate(lines):
        y = height_in - 0.24 - (j + 1) * pitch
        if s is not None:
            ax.text(
                label_w - 0.06,
                y + sq / 2,
                s,
                fontsize=_SMALL - 1.5,
                color=theme.ink2,
                ha="right",
                va="center",
            )
        for i, r in enumerate(line):
            colour = theme.base if r.arm == 0 else theme.cand
            ax.add_patch(
                _rect(
                    (label_w + i * sq + gap / 2, y + gap / 2),
                    sq - gap,
                    sq - gap,
                    colour,
                    alpha=1.0 if recorded else 0.55,
                )
            )


def _rect(xy: tuple[float, float], w: float, h: float, colour: str, alpha: float = 1.0) -> Any:
    from matplotlib.patches import Rectangle

    return Rectangle(xy, w, h, facecolor=colour, edgecolor="none", alpha=alpha)


def _draw_grid(ax: Axes, grid: SweepGrid, theme: Theme, width_in: float, height_in: float) -> None:
    """The swept grid as a dot matrix: a filled dot for a point that ran, a ring for one that did not."""
    ax.set_axis_off()
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, height_in)
    ys = grid.ys or (None,)
    ax.text(
        0,
        height_in - 0.06,
        f"swept: {grid.x_name}" + (f" × {grid.y_name}" if grid.ys else ""),
        fontsize=_SMALL - 1,
        color=theme.muted,
        va="top",
    )
    step = min(0.16, (width_in - 0.1) / max(len(grid.xs), 1), (height_in - 0.36) / len(ys))
    for j, y in enumerate(ys):
        for i, x in enumerate(grid.xs):
            ran = ((x, y) if grid.ys else (x,)) in grid.run
            ax.plot(
                [0.05 + (i + 0.5) * step],
                [height_in - 0.32 - (j + 0.5) * step],
                "o",
                markersize=min(5.0, step * 72 * 0.55),
                markerfacecolor=theme.ink2 if ran else "none",
                markeredgecolor=theme.ink2,
                markeredgewidth=0.8,
            )


def _draw_chips(
    ax: Axes, facts: Sequence[tuple[str, str]], theme: Theme, width_in: float, height_in: float
) -> None:
    """The facts as small rounded chips, a muted label then the value, flowed into lines."""
    from matplotlib.patches import FancyBboxPatch

    ax.set_axis_off()
    ax.set_xlim(0, width_in)
    ax.set_ylim(0, height_in)
    size = _SMALL - 0.5
    line_h, pad, gap = _CHIP_LINE_IN, 0.07, 0.07
    x, y = 0.0, height_in - 0.02 - line_h
    for label, value in facts:
        w = _text_w_in(label, size) + _text_w_in(value, size) + 2 * pad + 0.06
        if x > 0 and x + w > width_in:
            x, y = 0.0, y - line_h - _CHIP_GAP_IN
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                line_h,
                boxstyle="round,pad=0,rounding_size=0.06",
                facecolor=theme.tile,
                edgecolor="none",
            )
        )
        lab = ax.text(x + pad, y + line_h / 2, label, fontsize=size, color=theme.muted, va="center")
        ax.annotate(
            "  " + value, xy=(1, 0.5), xycoords=lab, fontsize=size, color=theme.ink, va="center"
        )
        x += w + gap


_CHIP_LINE_IN = 0.27
_CHIP_GAP_IN = 0.05


def _schematic_width(grid: SweepGrid | None) -> float:
    return 0.92 * WIDTH_IN - (1.55 if grid is not None else 0.0)


def _schematic_height(
    cells: Sequence[MetricEvidence], merge: bool, grid: SweepGrid | None
) -> float:
    runs = _runs(cells if merge else cells[:1])
    lines, _ = _schematic_rows(runs, _schematic_width(grid))
    height = 0.30 + len(lines) * _SQUARE_MAX_IN + 0.06
    if grid is not None:
        height = max(height, 0.40 + len(grid.ys or (None,)) * 0.16)
    return height


def _chip_lines(facts: Sequence[tuple[str, str]], width_in: float) -> int:
    size = _SMALL - 0.5
    x, lines = 0.0, 1
    for label, value in facts:
        w = _text_w_in(label, size) + _text_w_in(value, size) + 0.2
        if x > 0 and x + w > width_in:
            x, lines = 0.0, lines + 1
        x += w + 0.07
    return lines


def strip_height(
    cells: Sequence[MetricEvidence], *, merge: bool = False, grid: SweepGrid | None = None
) -> float:
    """The height in inches :func:`draw_design_strip` needs for *cells*."""
    points = len(grid.run) if grid is not None else 1
    lines = _chip_lines(design_facts(cells, points=points), 0.92 * WIDTH_IN)
    chips = lines * _CHIP_LINE_IN + (lines - 1) * _CHIP_GAP_IN + 0.08
    return 0.1 + _schematic_height(cells, merge, grid) + chips


def draw_design_strip(
    strip: FigureBase,
    cells: Sequence[MetricEvidence],
    theme: Theme,
    *,
    grid: SweepGrid | None = None,
    merge: bool = False,
) -> None:
    """Draw the experimental design into *strip*: run-order schematic, optional grid, fact chips.

    The top row is the run-order schematic (and, for a sweep, the grid's dot
    matrix at its right); the fact chips flow across the full width under it.
    *merge* takes the runs of every cell (a sweep, whose cells are different
    runs); otherwise the first cell's runs stand for all (metrics measured on the
    same runs).
    """
    h = strip_height(cells, merge=merge, grid=grid)
    left, right = 0.04 * WIDTH_IN, 0.96 * WIDTH_IN
    strip.add_artist(_hline(strip, 0.04, 0.96, 1 - 0.05 / h, theme.grid))
    runs = _runs(cells if merge else cells[:1])
    top_h = _schematic_height(cells, merge, grid)
    grid_w = 1.3 if grid is not None else 0.0
    sch_w = _schematic_width(grid)
    y_top = (h - 0.1 - top_h) / h
    ax = strip.add_axes((left / WIDTH_IN, y_top, sch_w / WIDTH_IN, top_h / h))
    _draw_schematic(ax, runs, theme, sch_w, top_h)
    if grid is not None:
        gx = strip.add_axes(((right - grid_w) / WIDTH_IN, y_top, grid_w / WIDTH_IN, top_h / h))
        _draw_grid(gx, grid, theme, grid_w, top_h)
    chips_h = h - 0.1 - top_h - 0.04
    cx = strip.add_axes((left / WIDTH_IN, 0.02, (right - left) / WIDTH_IN, chips_h / h))
    points = len(grid.run) if grid is not None else 1
    _draw_chips(cx, design_facts(cells, points=points), theme, right - left, chips_h)


def _hline(fig: FigureBase, x0: float, x1: float, y: float, colour: str) -> Any:
    from matplotlib.lines import Line2D

    return Line2D([x0, x1], [y, y], transform=fig.transSubfigure, color=colour, linewidth=0.8)


# --------------------------------------------------------------------------------------
# G1 Scorecard.


def summary_counts(metrics: Sequence[MetricEvidence]) -> str:
    """``2 improved · 0 regressed · 9 equivalent · 1 inconclusive``."""
    counts = dict.fromkeys(VerdictKind, 0)
    for m in metrics:
        counts[m.verdict.kind] += 1
    return " · ".join(f"{counts[k]} {k}" for k in VerdictKind)


def draw_scorecard(
    metrics: Sequence[MetricEvidence],
    theme: Theme = LIGHT,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    per_row: int = 3,
) -> Figure:
    """G1: one tile per (primary) metric: big effect, CI, mini effect bar, verdict, footer."""
    import matplotlib as mpl
    from matplotlib.patches import FancyBboxPatch

    with mpl.rc_context(_rc()):
        n = len(metrics)
        cols = max(1, min(per_row, n))
        rows = math.ceil(n / cols)
        tile_h = 2.05
        head = 0.95 if subtitle else 0.7
        height = head + rows * (tile_h + 0.18) + 0.1
        root, fig, strip = _figure_with_strip(height, theme, strip_height(metrics))
        _title(fig, title or summary_counts(metrics), subtitle, theme, height)
        gutter = 0.022
        left, right = 0.04, 0.96
        tile_w = (right - left - gutter * (cols - 1)) / cols
        rel = [m for m in metrics if m.kind == "positive"]
        lim_rel = effect_limits(rel) if rel else (-0.1, 0.1)
        for i, m in enumerate(metrics):
            r, c = divmod(i, cols)
            x0 = left + c * (tile_w + gutter)
            y0 = 1 - (head + (r + 1) * (tile_h + 0.18) - 0.18) / height
            h = tile_h / height
            ax = fig.add_axes((x0, y0, tile_w, h))
            ax.set_axis_off()
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.add_patch(
                FancyBboxPatch(
                    (0, 0),
                    1,
                    1,
                    boxstyle="round,pad=0,rounding_size=0.04",
                    transform=ax.transAxes,
                    facecolor=theme.tile,
                    edgecolor="none",
                    mutation_aspect=tile_w * WIDTH_IN / (tile_h),
                )
            )
            colour = theme.verdict_colour(m.verdict.kind)
            ax.add_patch(
                FancyBboxPatch(
                    (0.06, 0.955),
                    0.18,
                    0.012,
                    boxstyle="round,pad=0,rounding_size=0.006",
                    facecolor=colour,
                    edgecolor="none",
                )
            )
            label = humanize(m.name) + (
                "  · primary"
                if m.primary and len(metrics) > 1 and not all(x.primary for x in metrics)
                else ""
            )
            ax.text(0.06, 0.86, label, fontsize=_BODY, color=theme.ink2, va="top", weight="normal")
            if isinstance(m.effect, ProportionEffect):
                ax.text(
                    0.06,
                    0.70,
                    fmt_counts(m.effect),
                    fontsize=_HERO - 5,
                    color=theme.ink,
                    va="center",
                    weight="bold",
                )
                sub = f"{fmt_effect(m)}   {fmt_ci(m)}"
            else:
                ax.text(
                    0.06,
                    0.70,
                    fmt_effect(m),
                    fontsize=_HERO,
                    color=theme.ink,
                    va="center",
                    weight="bold",
                )
                sub = fmt_ci(m)
            ax.text(0.06, 0.535, sub, fontsize=_SMALL, color=theme.ink2, va="center")
            # Mini effect bar on the shared axis.
            bar = fig.add_axes((x0 + tile_w * 0.06, y0 + h * 0.355, tile_w * 0.88, h * 0.10))
            bar.set_facecolor(theme.tile)
            bar.set_axis_off()
            lim = lim_rel if m.kind == "positive" else effect_limits([m])
            _effect_axis(bar, m, lim, theme, ticks=False)
            bar.set_ylim(-1, 1)
            bar.plot(lim, [0, 0], color=theme.grid, lw=1.2, zorder=0.5, solid_capstyle="round")
            _ci_marks(bar, 0, m.effect, colour, theme, hollow=not m.fdr_pass, size=7)
            for x, ha in ((lim[0], "left"), (0.0, "center"), (lim[1], "right")):
                lab = "0" if x == 0 else fmt_signed(display(m, x), 0) + unit_suffix(m)
                bar.text(
                    x,
                    -1.25,
                    lab,
                    ha=ha,
                    va="top",
                    fontsize=_SMALL - 1.5,
                    color=theme.muted,
                    clip_on=False,
                )
            _chip(ax, 0.06, 0.19, m, theme, size=_BODY + 0.5)
            ax.text(
                0.06, 0.075, method_line(m), fontsize=_SMALL - 0.5, color=theme.muted, va="center"
            )
        if strip is not None:
            draw_design_strip(strip, metrics, theme)
        return root


# --------------------------------------------------------------------------------------
# G2 Forest plot.


def draw_forest(
    metrics: Sequence[MetricEvidence],
    theme: Theme = LIGHT,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    labels: Sequence[str] | None = None,
) -> Figure:
    """G2: one row per metric or sweep point, sorted by effect, on the shared axis.

    All rows must share an axis kind (relative % or pp). Each row shows the point,
    the 90 % (thick) and 95 % (thin) CI, the ±Δ band, the effect and the verdict.
    A row whose metric fails the FDR check is hollow; a primary metric is bold.
    """
    import matplotlib as mpl

    with mpl.rc_context(_rc()):
        names = list(labels) if labels is not None else [humanize(m.name) for m in metrics]
        order = sorted(range(len(metrics)), key=lambda i: metrics[i].effect.estimate)
        n = len(metrics)
        row_h = 0.34
        if subtitle is None:
            hollow = " · hollow: fails FDR" if any(not m.fdr_pass for m in metrics) else ""
            subtitle = f"Shaded: margin {fmt_margin(metrics[0])} · thick: decision CI (90 %) · thin: 95 % CI{hollow}"
        head = 1.25
        foot = 0.45
        height = head + n * row_h + foot
        root, fig, strip = _figure_with_strip(height, theme, strip_height(metrics))
        if title is None:
            moved = sum(
                m.verdict.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED) for m in metrics
            )
            same = sum(m.verdict.kind == VerdictKind.EQUIVALENT for m in metrics)
            if same == n:
                title = f"All {n} equivalent within {fmt_margin(metrics[0])}"
            else:
                title = f"{moved} of {n} moved, {same} equivalent within {fmt_margin(metrics[0])}"
        _title(fig, title, subtitle, theme, height)
        ax = _axes(fig, (0.30, foot / height, 0.40, n * row_h / height), theme)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_yticks([])
        lim = effect_limits(metrics)
        _effect_axis(ax, metrics[0], lim, theme)
        for row, i in enumerate(reversed(order)):
            m = metrics[i]
            y = row
            y_rev = n - 1 - y
            if row % 2 == 0:
                ax.axhspan(
                    y_rev - 0.5,
                    y_rev + 0.5,
                    xmin=-0.65,
                    xmax=1.65,
                    color=theme.tile,
                    zorder=-1,
                    clip_on=False,
                    lw=0,
                )
            colour = theme.verdict_colour(m.verdict.kind)
            _ci_marks(ax, y_rev, m.effect, colour, theme, hollow=not m.fdr_pass, size=7)
            trans = ax.get_yaxis_transform()
            ax.text(
                -0.04,
                y_rev,
                names[i],
                transform=trans,
                ha="right",
                va="center",
                fontsize=_BODY,
                color=theme.ink,
                weight="bold" if m.primary else "normal",
            )
            ax.text(
                1.04,
                y_rev,
                fmt_effect(m),
                transform=trans,
                ha="left",
                va="center",
                fontsize=_BODY,
                color=theme.ink,
            )
            g = ax.text(
                1.30,
                y_rev,
                m.verdict.glyph,
                transform=trans,
                ha="left",
                va="center",
                fontsize=_BODY,
                color=colour,
                weight="bold",
            )
            ax.annotate(
                " " + m.verdict.word,
                xy=(1, 0.5),
                xycoords=g,
                ha="left",
                va="center",
                fontsize=_BODY,
                color=theme.ink2,
            )
        ax.text(
            -0.04,
            1.0,
            "metric",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=_SMALL,
            color=theme.muted,
        )
        ax.text(
            1.04,
            1.0,
            "effect",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=_SMALL,
            color=theme.muted,
        )
        ax.text(
            1.30,
            1.0,
            "verdict",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=_SMALL,
            color=theme.muted,
        )
        if strip is not None:
            draw_design_strip(strip, metrics, theme)
        return root


# --------------------------------------------------------------------------------------
# G3 Estimation plot.


def draw_estimation(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G3: every sample per arm (swarm, median tick, slopes when paired) + the effect's distribution."""
    import matplotlib as mpl

    if not isinstance(m.effect, Effect):
        raise TypeError("draw_estimation needs a continuous metric")
    e = m.effect
    with mpl.rc_context(_rc()):
        height = 4.4
        root, fig, strip = _figure_with_strip(height, theme, strip_height([m]))
        _title(fig, title or headline(m), f"{e.method} · {method_line(m)}", theme, height)
        bottom, top = 0.5 / height, 1 - 1.15 / height
        ax = _axes(fig, (0.09, bottom, 0.50, top - bottom), theme)
        _hgrid(ax, theme)
        b, c = m.base[np.isfinite(m.base)], m.cand[np.isfinite(m.cand)]
        both = np.concatenate([b, c])
        span = float(np.ptp(both)) or 1.0
        xb = 0 + _swarm(b, 0.28, span)
        xc = 1 + _swarm(c, 0.28, span)
        if m.paired and len(m.base) == len(m.cand):
            keep = np.isfinite(m.base) & np.isfinite(m.cand)
            pb, pc = m.base[keep], m.cand[keep]
            for vb, vc in zip(pb, pc, strict=True):
                better = (vc - vb) * m.sign > 0
                ax.plot(
                    [0.36, 0.64],
                    [vb, vc],
                    color=theme.better if better else theme.worse,
                    alpha=0.45,
                    lw=1.0,
                    zorder=1,
                )
        ring = {"markeredgecolor": theme.surface, "markeredgewidth": 0.9}
        ax.plot(xb, b, "o", color=theme.base, markersize=5.5, zorder=3, **ring)
        ax.plot(xc, c, "o", color=theme.cand, markersize=5.5, zorder=3, **ring)
        for x, v in ((0, b), (1, c)):
            med = float(np.median(v))
            ax.plot(
                [x - 0.32, x + 0.32],
                [med, med],
                color=theme.ink,
                lw=2.0,
                solid_capstyle="round",
                zorder=4,
            )
        ax.set_xlim(-0.55, 1.55)
        ax.set_xticks([0, 1], [f"base  n={len(b)}", f"candidate  n={len(c)}"])
        ax.set_ylim(both.min() - 0.08 * span, both.max() + 0.08 * span)
        ax.set_ylabel(m.units or m.name, color=theme.ink2, fontsize=_SMALL)
        ax.tick_params(axis="x", labelsize=_BODY, colors=theme.ink)
        # Effect panel.
        ex = _axes(fig, (0.70, bottom, 0.22, top - bottom), theme)
        ex.spines["bottom"].set_visible(False)
        lim = effect_limits([m], pad=0.25)
        if e.bootstrap is not None:
            lo, hi = np.percentile(e.bootstrap, [0.1, 99.9])
            lim = (min(lim[0], lo), max(lim[1], hi))
        _effect_axis(ex, m, lim, theme, vertical=True)
        ex.yaxis.tick_right()
        ex.set_xlim(-0.75, 1.1)
        ex.set_xticks([])
        colour = theme.verdict_colour(m.verdict.kind)
        if e.bootstrap is not None:
            grid = np.linspace(lim[0], lim[1], 300)
            dens = _kde(e.bootstrap, grid)
            dens = dens / dens.max() * 0.75
            ex.fill_betweenx(grid, 0.2, 0.2 + dens, color=colour, alpha=0.22, lw=0, zorder=2)
            outline = np.where(dens > _DENSITY_FLOOR, 0.2 + dens, np.nan)
            ex.plot(outline, grid, color=colour, lw=1.0, alpha=0.8, zorder=2)
        _ci_marks(ex, 0.2, e, colour, theme, vertical=True, size=8)
        ex.text(
            0.5,
            1.02,
            "effect",
            transform=ex.transAxes,
            ha="center",
            va="bottom",
            fontsize=_SMALL,
            color=theme.muted,
        )
        ex.text(
            0.05,
            e.estimate,
            f"{fmt_effect(m)} ",
            ha="right",
            va="center",
            fontsize=_BODY,
            color=theme.ink,
            weight="bold",
        )
        _chip(ex, 0.0, -0.08, m, theme, size=_BODY)
        if strip is not None:
            draw_design_strip(strip, [m], theme)
        return root


# --------------------------------------------------------------------------------------
# G4 Raincloud + shift function.


def draw_raincloud_shift(
    m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None
) -> Figure:
    """G4: half-violin, box and raw points per arm; under it the decile shift function."""
    import matplotlib as mpl

    scale = "log" if m.kind == "positive" else "diff"
    sf = shift_function(m.base, m.cand, scale=scale, paired=m.paired)
    with mpl.rc_context(_rc()):
        height = 5.6
        fig = _figure(height, theme)
        _title(
            fig,
            title or _shift_title(m, sf),
            "Distribution of each arm (top) · change at each decile, 95 % bootstrap CI (bottom)",
            theme,
            height,
        )
        top = 1 - 1.1 / height
        mid = 0.52
        ax = _axes(fig, (0.16, mid + 0.04, 0.78, top - mid - 0.04), theme)
        ax.set_yticks([])
        ax.spines["bottom"].set_color(theme.grid)
        b, c = m.base[np.isfinite(m.base)], m.cand[np.isfinite(m.cand)]
        both = np.concatenate([b, c])
        lo, hi = both.min(), both.max()
        pad = 0.05 * (hi - lo or 1.0)
        grid = np.linspace(lo - pad, hi + pad, 400)
        rng = np.random.default_rng(7)
        for row, (vals, colour, name) in enumerate(
            ((c, theme.cand, "candidate"), (b, theme.base, "base"))
        ):
            y0 = row * 1.0
            dens = _kde(vals, grid)
            dens = dens / dens.max() * 0.55
            ax.fill_between(grid, y0 + 0.08, y0 + 0.08 + dens, color=colour, alpha=0.25, lw=0)
            ax.plot(grid, y0 + 0.08 + dens, color=colour, lw=1.2)
            q1, med, q3 = np.percentile(vals, [25, 50, 75])
            ax.plot([q1, q3], [y0, y0], color=theme.ink, lw=3.0, solid_capstyle="round", zorder=4)
            ax.plot(
                [med],
                [y0],
                marker="o",
                markersize=6,
                color=theme.surface,
                markeredgecolor=theme.ink,
                markeredgewidth=1.6,
                zorder=5,
            )
            jitter = rng.uniform(-0.16, -0.06, len(vals))
            ax.plot(
                vals,
                y0 + jitter - 0.04,
                "o",
                color=colour,
                markersize=3.6,
                alpha=0.75,
                markeredgewidth=0,
                zorder=3,
            )
            ax.text(
                -0.015,
                y0 + 0.15,
                name,
                transform=ax.get_yaxis_transform(),
                ha="right",
                va="center",
                fontsize=_BODY,
                color=theme.ink,
            )
        ax.set_ylim(-0.35, 1.75)
        ax.set_xlim(grid[0], grid[-1])
        ax.set_xlabel(m.units or m.name, fontsize=_SMALL, color=theme.ink2)
        # Shift function.
        sx = _axes(fig, (0.16, 0.10, 0.78, mid - 0.18), theme)
        _hgrid(sx, theme)
        x = np.arange(len(sf.probs))
        lim = (min(sf.low.min(), -_delta(m)) * 1.15, max(sf.high.max(), _delta(m)) * 1.15)
        _effect_axis(sx, m, lim, theme, vertical=True)
        sx.plot(x, sf.diff, color=theme.muted, lw=1.0, zorder=2)
        for i in range(len(x)):
            excl = sf.low[i] > 0 or sf.high[i] < 0
            good = sf.diff[i] * m.sign > 0
            colour = (theme.better if good else theme.worse) if excl else theme.muted
            sx.plot(
                [x[i], x[i]],
                [sf.low[i], sf.high[i]],
                color=colour,
                lw=2.2,
                solid_capstyle="round",
                zorder=3,
            )
            sx.plot(
                [x[i]],
                [sf.diff[i]],
                "o",
                color=colour,
                markersize=7,
                markeredgecolor=theme.surface,
                markeredgewidth=1.5,
                zorder=4,
            )
        sx.set_xticks(x, [f"p{round(100 * p)}" for p in sf.probs])
        sx.set_xlim(-0.5, len(x) - 0.5)
        return fig


def _delta(m: MetricEvidence) -> float:
    return math.log1p(m.margin) if m.kind == "positive" else m.margin


def _shift_title(m: MetricEvidence, sf: ShiftFunction) -> str:
    diff = sf.diff
    probs = sf.probs
    i_med = probs.index(0.5)
    tail = len(probs) - 1
    name = humanize(m.name)
    med, top = display(m, diff[i_med]), display(m, diff[tail])
    unit = unit_suffix(m)
    return f"{name}: median {fmt_signed(med, 0)}{unit}, p{round(100 * probs[tail])} {fmt_signed(top, 0)}{unit}"


# --------------------------------------------------------------------------------------
# G5 Waffle.


def _waffle_columns(n: int) -> int:
    """Squares per waffle row: one row up to 20 runs, then about two rows, wider past 30 and 60."""
    for limit, cols in ((60, 20), (30, 15)):
        if n > limit:
            return cols
    one_row = 20
    return n if n <= one_row else max(10, math.ceil(n / 2))


def draw_waffle(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G5: one square per run per arm; Wilson CI per arm; difference CI; rule of three at 0."""
    import matplotlib as mpl
    from matplotlib.patches import FancyBboxPatch

    e = m.effect
    if not isinstance(e, ProportionEffect):
        raise TypeError("draw_waffle needs a binary metric")
    good_is_one = m.direction == "maximize"
    event = humanize(m.name).lower()
    bad_word = "failures" if good_is_one else event
    with mpl.rc_context(_rc()):
        nmax = max(e.n_base, e.n_cand)
        cols = _waffle_columns(nmax)
        rows_b, rows_c = math.ceil(e.n_base / cols), math.ceil(e.n_cand / cols)
        cell = 0.22
        block_h = lambda r: r * cell + 0.42  # noqa: E731
        height = 1.15 + block_h(rows_b) + block_h(rows_c) + 1.25
        root, fig, strip = _figure_with_strip(height, theme, strip_height([m]))
        _title(fig, title or headline(m), f"One square per run · {method_line(m)}", theme, height)
        y_cursor = height - 1.15
        grid_w_in = cols * cell
        for arm, (k, n, colour, wil) in (
            ("base", (e.k_base, e.n_base, theme.base, e.wilson_base)),
            ("candidate", (e.k_cand, e.n_cand, theme.cand, e.wilson_cand)),
        ):
            rows = math.ceil(n / cols)
            bh = block_h(rows)
            ax = fig.add_axes(
                (
                    0.32 / WIDTH_IN,
                    (y_cursor - bh) / height,
                    (grid_w_in + 0.1) / WIDTH_IN,
                    bh / height,
                )
            )
            ax.set_axis_off()
            ax.set_xlim(0, grid_w_in + 0.1)
            ax.set_ylim(0, bh)
            ax.text(
                0, bh - 0.12, arm, fontsize=_BODY, color=theme.ink, va="center", weight="normal"
            )
            outcomes = [1] * k + [0] * (n - k)
            for idx, out in enumerate(outcomes):
                r, cc = divmod(idx, cols)
                x = cc * cell
                y = bh - 0.42 - (r + 1) * cell + 0.03
                good = (out == 1) == good_is_one
                face = colour if good else theme.worse
                ax.add_patch(
                    FancyBboxPatch(
                        (x + 0.02, y + 0.02),
                        cell - 0.04,
                        cell - 0.04,
                        boxstyle="round,pad=0,rounding_size=0.03",
                        facecolor=face,
                        edgecolor="none",
                    )
                )
                if not good:
                    ax.plot(
                        [x + 0.06, x + cell - 0.06],
                        [y + 0.06, y + cell - 0.06],
                        color=theme.surface,
                        lw=1.3,
                    )
                    ax.plot(
                        [x + 0.06, x + cell - 0.06],
                        [y + cell - 0.06, y + 0.06],
                        color=theme.surface,
                        lw=1.3,
                    )
            # Wilson CI on a 0–100 % strip at the right.
            sx = fig.add_axes((0.64, (y_cursor - bh + 0.10) / height, 0.32, 0.30 / height))
            sx.set_axis_off()
            sx.set_xlim(-0.02, 1.02)
            sx.set_ylim(-1, 1)
            sx.plot([0, 1], [0, 0], color=theme.grid, lw=3, solid_capstyle="round")
            sx.plot([wil.low, wil.high], [0, 0], color=colour, lw=4.5, solid_capstyle="round")
            sx.plot(
                [k / n],
                [0],
                "o",
                color=colour,
                markersize=8,
                markeredgecolor=theme.surface,
                markeredgewidth=1.5,
            )
            rate = f"{k}/{n} · {100 * k / n:.0f} %   95 % CI {100 * wil.low:.0f}–{100 * wil.high:.0f} %"
            fig.text(
                0.64,
                (y_cursor - 0.12) / height,
                rate,
                fontsize=_SMALL,
                color=theme.ink2,
                va="center",
            )
            y_cursor -= bh + 0.05
        # Difference CI.
        dx = _axes(fig, (0.32 / WIDTH_IN + 0.02, 0.62 / height, 0.55, 0.30 / height), theme)
        dx.set_yticks([])
        dx.set_ylim(-1, 1)
        lim = effect_limits([m], pad=0.2)
        _effect_axis(dx, m, lim, theme)
        colour = theme.verdict_colour(m.verdict.kind)
        _ci_marks(dx, 0, e, colour, theme, size=8)
        dx.text(
            0,
            1.6,
            f"difference {fmt_effect(m)}  ·  {fmt_ci(m)}",
            transform=dx.get_yaxis_transform(),
            fontsize=_SMALL,
            color=theme.ink2,
            va="center",
        )
        _chip(dx, 1.06, 0.3, m, theme)
        bad = e.n_cand - e.k_cand if good_is_one else e.k_cand
        if bad == 0:
            note = f"0 {bad_word} in {e.n_cand} candidate runs: rate ≤ {100 * e.bad_upper:.1f} % (95 %, exact; rule of three ≈ {100 * 3 / e.n_cand:.1f} %)"
        else:
            note = (
                f"candidate {bad_word} rate ≤ {100 * e.bad_upper:.1f} % (95 % upper bound, exact)"
            )
        fig.text(0.04, 0.16 / height, note, fontsize=_SMALL, color=theme.muted, va="center")
        if strip is not None:
            draw_design_strip(strip, [m], theme)
        return root


# --------------------------------------------------------------------------------------
# G6 Sweep panel.


def draw_sweep(
    cells: Sequence[MetricEvidence],
    xs: Sequence[float],
    theme: Theme = LIGHT,
    *,
    x_name: str = "x",
    title: str | None = None,
) -> Figure:
    """G6: top, both arms' median with a 95 % order-statistic CI ribbon; bottom, effect per point."""
    import matplotlib as mpl

    with mpl.rc_context(_rc()):
        height = 5.6
        sweep_grid = SweepGrid(tuple(xs), None, frozenset((v,) for v in xs), x_name)
        root, fig, strip = _figure_with_strip(
            height, theme, strip_height(cells, merge=True, grid=sweep_grid)
        )
        m0 = cells[0]
        moved = [
            m for m in cells if m.verdict.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED)
        ]
        if title is None:
            title = f"{humanize(m0.name)}: {len(moved)} of {len(cells)} {x_name} points moved"
        _title(
            fig,
            title,
            f"Median and 95 % CI per {x_name} point (top) · effect per point, 90 %/95 % CI (bottom)",
            theme,
            height,
        )
        x = np.asarray(xs, dtype=float)
        top = 1 - 1.1 / height
        ax = _axes(fig, (0.12, 0.52, 0.76, top - 0.52), theme)
        _hgrid(ax, theme)
        for arm, colour in (("base", theme.base), ("cand", theme.cand)):
            meds, los, his = [], [], []
            for m in cells:
                vals = getattr(m, arm)
                q = quantile_ci(vals, 0.5)
                meds.append(q.estimate)
                los.append(q.low if q.low is not None else np.nanmin(vals))
                his.append(q.high if q.high is not None else np.nanmax(vals))
            ax.fill_between(x, los, his, color=colour, alpha=0.18, lw=0)
            ax.plot(x, meds, color=colour, lw=2.0, solid_capstyle="round")
            ax.plot(
                x,
                meds,
                "o",
                color=colour,
                markersize=5,
                markeredgecolor=theme.surface,
                markeredgewidth=1.2,
            )
            ax.text(
                x[-1] + 0.015 * np.ptp(x),
                meds[-1],
                " " + ("base" if arm == "base" else "candidate"),
                ha="left",
                va="center",
                fontsize=_BODY,
                color=theme.ink,
            )
        ax.set_xlim(x[0] - 0.03 * np.ptp(x), x[-1] + 0.03 * np.ptp(x))
        ax.set_xticklabels([])
        ax.set_ylabel(m0.units or m0.name, fontsize=_SMALL, color=theme.ink2)
        ex = _axes(fig, (0.12, 0.11, 0.76, 0.34), theme)
        lim = effect_limits(cells, pad=0.15)
        _effect_axis(ex, m0, lim, theme, vertical=True)
        ex.grid(axis="y", color=theme.grid, linewidth=0.6)
        for xi, m in zip(x, cells, strict=True):
            colour = theme.verdict_colour(m.verdict.kind)
            _ci_marks(ex, xi, m.effect, colour, theme, vertical=True, hollow=not m.fdr_pass, size=7)
        ex.set_xlim(*ax.get_xlim())
        ex.set_xticks(x, [f"{v:g}" for v in x])
        ex.set_xlabel(x_name, fontsize=_SMALL, color=theme.ink2)
        ex.set_ylabel("effect", fontsize=_SMALL, color=theme.ink2)
        if strip is not None:
            draw_design_strip(strip, cells, theme, merge=True, grid=sweep_grid)
        return root


# --------------------------------------------------------------------------------------
# G7 Effect heatmap.


def draw_heatmap(
    cells: Sequence[Sequence[MetricEvidence]],
    xs: Sequence[object],
    ys: Sequence[object],
    theme: Theme = LIGHT,
    *,
    x_name: str = "x",
    y_name: str = "y",
    title: str | None = None,
) -> Figure:
    """G7: effect per (y, x) cell, diverging blue (better) – orange (worse) centred on 0.

    A cell whose CI crosses the margin (inconclusive) is hatched; each cell carries
    its glyph and effect. ``cells[j][i]`` is the cell at ``ys[j]``, ``xs[i]``.
    """
    import matplotlib as mpl
    from matplotlib.colors import LinearSegmentedColormap, to_rgb
    from matplotlib.patches import Rectangle

    with mpl.rc_context(_rc()):
        ny, nx = len(ys), len(xs)
        cell_in = min(0.9, 5.4 / nx)
        height = 1.35 + ny * cell_in * 0.8 + 0.9
        flat = [m for row in cells for m in row]
        sweep_grid = SweepGrid(
            tuple(xs), tuple(ys), frozenset((x, y) for x in xs for y in ys), x_name, y_name
        )
        root, fig, strip = _figure_with_strip(
            height, theme, strip_height(flat, merge=True, grid=sweep_grid)
        )
        flat = [m for row in cells for m in row]
        m0 = flat[0]
        n_better = sum(m.verdict.kind == VerdictKind.IMPROVED for m in flat)
        n_worse = sum(m.verdict.kind == VerdictKind.REGRESSED for m in flat)
        _title(
            fig,
            title
            or f"{humanize(m0.name)}: {n_better} cells better, {n_worse} worse of {len(flat)}",
            f"Effect per cell · blue better, orange worse · hatched: CI crosses {fmt_margin(m0)}",
            theme,
            height,
        )
        oriented = np.array([[m.sign * m.effect.estimate for m in row] for row in cells])
        reach = max(float(np.abs(oriented).max()), _delta(m0)) or 1.0
        cmap = LinearSegmentedColormap.from_list("bo", [theme.worse, theme.mid, theme.cand])
        grid_w = nx * cell_in / WIDTH_IN
        ax = fig.add_axes((0.16, 0.9 / height, grid_w, ny * cell_in * 0.8 / height))
        ax.set_facecolor(theme.surface)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=theme.ink2, labelsize=_SMALL, length=0)
        for j, row in enumerate(cells):
            for i, m in enumerate(row):
                val = oriented[j, i] / reach
                rgb = to_rgb(cmap(0.5 + 0.5 * val))
                ax.add_patch(
                    Rectangle((i + 0.03, j + 0.03), 0.94, 0.94, facecolor=rgb, edgecolor="none")
                )
                if m.verdict.kind == VerdictKind.INCONCLUSIVE:
                    ax.add_patch(
                        Rectangle(
                            (i + 0.03, j + 0.03),
                            0.94,
                            0.94,
                            facecolor="none",
                            edgecolor=theme.surface,
                            hatch="////",
                            lw=0,
                        )
                    )
                lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                ink = "#111111" if lum > 0.55 else "#ffffff"  # noqa: PLR2004
                ax.text(
                    i + 0.5,
                    j + 0.60,
                    m.verdict.glyph,
                    ha="center",
                    va="center",
                    fontsize=_BODY + 1,
                    color=ink,
                    weight="bold",
                )
                ax.text(
                    i + 0.5,
                    j + 0.32,
                    fmt_effect(m).replace(" ", ""),
                    ha="center",
                    va="center",
                    fontsize=_SMALL - 0.5,
                    color=ink,
                )
        ax.set_xlim(0, nx)
        ax.set_ylim(0, ny)
        ax.set_xticks(np.arange(nx) + 0.5, [str(v) for v in xs])
        ax.set_yticks(np.arange(ny) + 0.5, [str(v) for v in ys])
        ax.set_xlabel(x_name, fontsize=_SMALL, color=theme.ink2)
        ax.set_ylabel(y_name, fontsize=_SMALL, color=theme.ink2)
        # Colour key.
        kx = fig.add_axes((0.16 + grid_w + 0.05, 0.9 / height, 0.025, ny * cell_in * 0.8 / height))
        kx.imshow(
            np.linspace(1, 0, 256)[:, None], aspect="auto", cmap=cmap, extent=(0, 1, -reach, reach)
        )
        kx.set_xticks([])
        kx.yaxis.tick_right()
        kx.tick_params(colors=theme.ink2, labelsize=_SMALL - 0.5, length=0)
        for s in kx.spines.values():
            s.set_visible(False)
        t = [-reach, 0, reach]
        kx.set_yticks(t, [f"{fmt_signed(display(m0, v * m0.sign), 0)}{unit_suffix(m0)}" for v in t])
        kx.text(
            0.5,
            reach * 1.08,
            "better",
            ha="center",
            va="bottom",
            fontsize=_SMALL - 0.5,
            color=theme.ink2,
        )
        kx.text(
            0.5,
            -reach * 1.08,
            "worse",
            ha="center",
            va="top",
            fontsize=_SMALL - 0.5,
            color=theme.ink2,
        )
        if strip is not None:
            draw_design_strip(strip, flat, theme, merge=True, grid=sweep_grid)
        return root


# --------------------------------------------------------------------------------------
# G8 Power bar.


def draw_power(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G8: the minimum detectable effect against the margin, and the runs that would close the gap."""
    import matplotlib as mpl

    v = m.verdict
    if v.mde is None:
        raise ValueError("draw_power needs a verdict with an MDE")
    with mpl.rc_context(_rc()):
        height = 2.0
        fig = _figure(height, theme)
        mde_d = abs(display(m, v.mde))
        delta_d = abs(display(m, v.margin))
        unit = unit_suffix(m)
        add = v.add_runs
        if title is None:
            title = (
                f"Underpowered: add ~{add} runs per arm"
                if add
                else "Power is enough for the margin"
            )
        _title(
            fig,
            title,
            f"Smallest change this run can detect (80 % power) against the margin of {fmt_margin(m)}",
            theme,
            height,
        )
        ax = _axes(fig, (0.04, 0.22, 0.70, 0.22), theme)
        ax.set_yticks([])
        top = max(mde_d, delta_d) * 1.25
        ax.set_xlim(0, top)
        ax.set_ylim(-1, 1)
        ax.barh(
            [0],
            [mde_d],
            height=0.9,
            color=theme.unsure if v.underpowered else theme.better,
            alpha=0.9,
        )
        ax.axvline(delta_d, color=theme.ink, lw=1.6)
        ax.text(
            delta_d,
            1.25,
            f"margin {delta_d:g}{unit}",
            ha="center",
            va="bottom",
            fontsize=_SMALL,
            color=theme.ink,
        )
        ax.text(
            mde_d,
            0,
            f"  MDE {mde_d:.1f}{unit}",
            ha="left",
            va="center",
            fontsize=_BODY,
            color=theme.ink,
            weight="bold",
        )
        ax.tick_params(axis="x", labelsize=_SMALL)
        if v.runs_needed:
            fig.text(
                0.78,
                0.33,
                f"n = {v.n} → ~{v.runs_needed}",
                fontsize=_BODY + 2,
                color=theme.ink,
                weight="bold",
                va="center",
            )
            fig.text(
                0.78,
                0.18,
                "units per arm to reach Δ",
                fontsize=_SMALL,
                color=theme.ink2,
                va="center",
            )
        return fig


# --------------------------------------------------------------------------------------
# G9 Diagnostics.


def draw_diagnostics(
    m: MetricEvidence,
    theme: Theme = LIGHT,
    *,
    order_base: Sequence[int] | None = None,
    order_cand: Sequence[int] | None = None,
    aa_band: tuple[float, float] | None = None,
    title: str | None = None,
) -> Figure:
    """G9: value against run order by arm (marker by shard), each arm's trend; an A/A null band.

    *order_base* / *order_cand* give each sample's run index (default: its position;
    interleaved when paired). *aa_band* is an A/A effect interval (relative for a
    positive metric) drawn as a band around the base median.
    """
    import matplotlib as mpl

    b, c = m.base, m.cand
    if order_base is None or order_cand is None:
        if m.paired:
            order_base, order_cand = list(range(0, 2 * len(b), 2)), list(range(1, 2 * len(c), 2))
        else:
            order_base, order_cand = list(range(len(b))), list(range(len(b), len(b) + len(c)))
    shard_markers = ("o", "s", "D", "^", "v", "P", "X")
    with mpl.rc_context(_rc()):
        height = 3.6
        fig = _figure(height, theme)
        slopes = []
        for vals, order in ((b, order_base), (c, order_cand)):
            ok = np.isfinite(vals)
            xo = np.asarray(order, dtype=float)[ok]
            if ok.sum() > 2 and np.ptp(xo) > 0:  # noqa: PLR2004
                slope, icpt = np.polyfit(xo, vals[ok], 1)
                level = np.nanmedian(vals) or 1.0
                slopes.append((slope, icpt, xo, 100 * slope * np.ptp(xo) / abs(level)))
            else:
                slopes.append(None)
        drift = [s[3] for s in slopes if s is not None]
        if title is None:
            worst = max(drift, key=abs) if drift else 0.0
            title = (
                "No drift within either arm"
                if abs(worst) < 100 * m.margin
                else f"Drift of {fmt_signed(worst, 0)} % across one arm"
            )
        _title(
            fig,
            title,
            "Value against run order · line: least-squares trend per arm · marker shape: shard",
            theme,
            height,
        )
        ax = _axes(fig, (0.09, 0.14, 0.78, 1 - 1.15 / height - 0.14), theme)
        _hgrid(ax, theme)
        if aa_band is not None and np.isfinite(b).any():
            med = float(np.nanmedian(b))
            lo, hi = (
                (med * (1 + aa_band[0]), med * (1 + aa_band[1]))
                if m.kind == "positive"
                else (med + aa_band[0], med + aa_band[1])
            )
            ax.axhspan(lo, hi, color=theme.band, lw=0, zorder=0)
            ax.text(
                1.0,
                hi,
                " A/A noise",
                transform=ax.get_yaxis_transform(),
                fontsize=_SMALL,
                color=theme.ink2,
                va="bottom",
            )
        for (vals, order, colour, name, cl), sl in zip(
            (
                (b, order_base, theme.base, "base", m.clusters[0]),
                (
                    c,
                    order_cand,
                    theme.cand,
                    "candidate",
                    m.clusters[1] if not m.paired else m.clusters[0],
                ),
            ),
            slopes,
            strict=True,
        ):
            xo = np.asarray(order, dtype=float)
            if cl is None:
                ax.plot(
                    xo,
                    vals,
                    "o",
                    color=colour,
                    markersize=5,
                    markeredgecolor=theme.surface,
                    markeredgewidth=0.8,
                    zorder=3,
                )
            else:
                labels = list(dict.fromkeys(cl.tolist()))
                for k, lab in enumerate(labels):
                    sel = cl == lab
                    ax.plot(
                        xo[sel],
                        vals[sel],
                        shard_markers[k % len(shard_markers)],
                        color=colour,
                        markersize=5,
                        markeredgecolor=theme.surface,
                        markeredgewidth=0.8,
                        zorder=3,
                    )
            if sl is not None:
                slope, icpt, xs_, _ = sl
                ax.plot(
                    [xs_.min(), xs_.max()],
                    [icpt + slope * xs_.min(), icpt + slope * xs_.max()],
                    color=colour,
                    lw=2.0,
                    zorder=4,
                )
                ax.text(
                    xs_.max(),
                    icpt + slope * xs_.max(),
                    f"  {name}",
                    ha="left",
                    va="center",
                    fontsize=_BODY,
                    color=theme.ink,
                )
        ax.set_xlabel("run order", fontsize=_SMALL, color=theme.ink2)
        ax.set_ylabel(m.units or m.name, fontsize=_SMALL, color=theme.ink2)
        return fig


# --------------------------------------------------------------------------------------
# Saving.


def save_both(draw: Callable[[Theme], Figure], out_dir: str | Path, stem: str) -> dict[str, Path]:
    """Draw *draw(theme)* in both themes; write ``{stem}-{light,dark}.{png,svg}`` to *out_dir*.

    Returns ``{"light": png, "dark": png, "light_svg": svg, "dark_svg": svg}``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for theme in THEMES:
        import matplotlib as mpl

        with mpl.rc_context(_rc()):
            fig = draw(theme)
            png = out / f"{stem}-{theme.name}.png"
            svg = out / f"{stem}-{theme.name}.svg"
            fig.savefig(png, dpi=DPI, facecolor=theme.surface)
            fig.savefig(svg, facecolor=theme.surface, metadata={"Date": None})
        paths[theme.name] = png
        paths[f"{theme.name}_svg"] = svg
    return paths
