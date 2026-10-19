"""The evidence graphics G1–G9 of ``docs/statistical_evidence.md`` §5, as matplotlib Figures.

Each ``draw_*`` function takes the :class:`~bencher.evidence_stats.MetricEvidence`
records it shows and a :class:`Theme` and returns a ``matplotlib.figure.Figure``
built without pyplot (no global backend state, safe in any process).
:func:`save_both` draws one graphic in the light and the dark theme and writes
each as a PNG at 2× (1600 px wide, shown at 800) and as an SVG.

The rules every graphic keeps:

* Show the data. A continuous metric shows every sample as a dot in a
  deterministic beeswarm column (base grey on the left, candidate blue on the
  right), a short thick median bar and ``n`` under each column; paired samples
  are joined by faint lines, green when the pair got better and orange when worse.
* The margin lives in data units: ±Δ is a shaded band around the base median on
  the metric's own axis, and the CI of the shift is a bracket beside the
  candidate column (thick: the decision CI; thin: the 95 % CI, only when wider).
* Little text: a title that states the finding, one big effect number with the
  verdict glyph, tick labels and column labels; nothing under 11 pt (15 px at the
  800 px display width). Everything else goes in the Markdown and the alt text.
* The run order shows as one row of small squares per shard under the panels
  (grey base, blue candidate, in execution order); no row when it was not recorded.
* Okabe–Ito colours, each backed by a glyph (▲ ▼ ≈ ?); text wears the theme's
  ink, never a data colour.
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
    shift_function,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

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

# Type scale (pt). The figure is 8 in shown 800 px wide: 1 pt is ~1.39 px on screen, so
# 11 pt is the 15 px floor.
_TITLE = 19
_HERO = 28
_LABEL = 13
_TICK = 11.5
_MIN_PT = 11

_ZERO = 1e-9
_DENSITY_FLOOR = 0.01  # below this the KDE outline is not drawn (no hairline at 0)
_SIDE_IN = 0.32  # left and right page margin
_HEAD_IN = 0.85  # title row height
_FOOT_IN = 0.18  # bottom margin


# --------------------------------------------------------------------------------------
# Words and numbers (the Markdown and the alt text use these too).


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


def _amount(m: MetricEvidence) -> str:
    size = display(m, m.effect.estimate)
    if m.kind == "positive":
        return f"{abs(size):.0f} %" if abs(size) >= 10 else f"{abs(size):.1f} %"  # noqa: PLR2004
    return f"{abs(size):.{_digits(m)}f}{unit_suffix(m)}"


def headline(m: MetricEvidence) -> str:
    """The finding as a Markdown heading: "Planning time is 18 % faster"."""
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
    raised = m.effect.estimate > 0
    amount = _amount(m)
    if v.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED):
        return f"{name} is {amount} {_direction_word(m, raised)}"
    if v.kind == VerdictKind.EQUIVALENT:
        if v.detail == "no change":
            return f"{name} is unchanged within {fmt_margin(m)}"
        return f"{name} is {amount} {_direction_word(m, raised)}, inside {fmt_margin(m)}"
    return f"{name}: not yet known ({fmt_effect(m)}, {fmt_ci(m)})"


def chart_title(m: MetricEvidence) -> str:
    """The finding in at most six words, for a chart: "Planning time 18 % faster"."""
    name = humanize(m.name)
    v = m.verdict
    if v.kind == VerdictKind.INCONCLUSIVE:
        return f"{name}: not known yet"
    if v.kind == VerdictKind.EQUIVALENT:
        return f"{name} unchanged" if v.detail == "no change" else f"{name}: {v.word}"
    if isinstance(m.effect, ProportionEffect):
        return f"{name} {v.word}"
    return f"{name} {_amount(m)} {_direction_word(m, m.effect.estimate > 0)}"


def method_line(m: MetricEvidence, *, with_test: bool = True) -> str:
    """``n=20 paired · BCa · MDE 4.1 %`` (no test name when not *with_test*)."""
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
        parts = [n, "BCa" if e.bootstrap is not None else "Welch t"] if with_test else [n]
    if m.verdict.mde is not None:
        parts.append(f"MDE {fmt_mde(m)}")
    return " · ".join(parts)


def fmt_mde(m: MetricEvidence) -> str:
    """The minimum detectable effect in the report's unit: ``4.1 %``."""
    mde = m.verdict.mde or 0.0
    value = 100 * math.expm1(mde) if m.kind == "positive" else display(m, mde)
    return f"{abs(value):.1f}{unit_suffix(m)}"


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


def summary_counts(metrics: Sequence[MetricEvidence]) -> str:
    """``2 improved · 0 regressed · 9 equivalent · 1 inconclusive``."""
    counts = dict.fromkeys(VerdictKind, 0)
    for m in metrics:
        counts[m.verdict.kind] += 1
    return " · ".join(f"{counts[k]} {k}" for k in VerdictKind)


def short_summary(metrics: Sequence[MetricEvidence]) -> str:
    """The verdict counts that are not zero, for a chart title: ``1 improved, 1 equivalent``."""
    if len(metrics) == 1:
        return chart_title(metrics[0])
    counts = dict.fromkeys(VerdictKind, 0)
    for m in metrics:
        counts[m.verdict.kind] += 1
    if counts[VerdictKind.EQUIVALENT] == len(metrics):
        return f"All {len(metrics)} unchanged"
    return ", ".join(f"{c} {k}" for k, c in counts.items() if c)


# --------------------------------------------------------------------------------------
# The design, as words for the Markdown (the graphic draws the run order instead).


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


def order_recorded(cells: Sequence[MetricEvidence]) -> bool:
    """Whether every run behind *cells* has a recorded run order."""
    runs = _runs(cells)
    return bool(runs) and all(r.order is not None for r in runs)


def shard_names(cells: Sequence[MetricEvidence]) -> list[str]:
    """The shards in the order the run-order rows draw them (row k is "VM k+1")."""
    return sorted({r.shard for r in _runs(cells) if r.shard is not None}, key=str)


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


def order_pattern(cells: Sequence[MetricEvidence]) -> str:
    """The run-order pattern of *cells*, or ``not recorded``."""
    return _order_pattern(_runs(cells)) if order_recorded(cells) else "not recorded"


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
    """The labelled facts of the design, from the first cell (and the cell count)."""
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


# --------------------------------------------------------------------------------------
# Page layout: every graphic is laid out in inches from the top-left corner.


class _Page:
    """A figure of fixed width whose axes are placed in inches from the top-left."""

    def __init__(self, height_in: float, theme: Theme) -> None:
        from matplotlib.figure import Figure

        self.h = height_in
        self.theme = theme
        self.fig = Figure(figsize=(WIDTH_IN, height_in), dpi=DPI, facecolor=theme.surface)
        self.fig.set_layout_engine("none")

    def axes(self, x: float, top: float, w: float, h: float) -> Axes:
        """An axes at *x* in from the left, *top* in from the top, *w* × *h* inches."""
        ax = self.fig.add_axes((x / WIDTH_IN, 1 - (top + h) / self.h, w / WIDTH_IN, h / self.h))
        ax.set_facecolor(self.theme.surface)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.tick_params(colors=self.theme.ink2, labelsize=_TICK, length=0, pad=5)
        ax.grid(visible=False)
        return ax

    def canvas(self, x: float, top: float, w: float, h: float) -> Axes:
        """A blank axes whose data units are inches (origin at its bottom-left)."""
        ax = self.axes(x, top, w, h)
        ax.set_axis_off()
        ax.set_xlim(0, w)
        ax.set_ylim(0, h)
        return ax

    def text(self, x: float, top: float, s: str, **kw: Any) -> Any:
        return self.fig.text(x / WIDTH_IN, 1 - top / self.h, s, **kw)

    def header(self, title: str, hero: MetricEvidence | None = None) -> None:
        """The title at the left; the big effect number with its glyph at the right."""
        t = self.theme
        room = WIDTH_IN - 2 * _SIDE_IN - 0.3
        if hero is not None:
            room -= _text_w_in(hero.verdict.glyph + " " + fmt_effect(hero), _HERO)
        size = _TITLE
        while size > _MIN_PT + 3 and _text_w_in(title, size) > room:
            size -= 1
        self.text(
            _SIDE_IN,
            0.22,
            title,
            ha="left",
            va="top",
            fontsize=size,
            weight="bold",
            color=t.ink,
        )
        if hero is not None:
            _hero(self, WIDTH_IN - _SIDE_IN, 0.16, hero, ha="right")


def _text_w_in(text: str, size: float) -> float:
    """A bold DejaVu/Open Sans line's width in inches, without a renderer (~0.66 em a glyph)."""
    return len(text) * size * 0.66 / 72.0


def _rc() -> dict:
    return {
        "font.family": "sans-serif",
        "font.sans-serif": list(FONT),
        "svg.fonttype": "path",
        "axes.unicode_minus": True,
    }


def _hero(
    page: _Page, x: float, top: float, m: MetricEvidence, *, ha: str, size: float = _HERO
) -> None:
    """The verdict glyph (in the verdict colour) and the effect (in ink), as one big line."""
    from matplotlib.text import Annotation

    t = page.theme
    colour = t.verdict_colour(m.verdict.kind)
    style = {"fontsize": size, "weight": "bold"}
    if ha == "right":
        anchor = page.text(x, top, fmt_effect(m), ha="right", va="top", color=t.ink, **style)
        tail = Annotation(
            m.verdict.glyph + " ",
            xy=(0, 0),
            xycoords=anchor,
            ha="right",
            va="bottom",
            color=colour,
            **style,
        )
    else:
        anchor = page.text(
            x, top, m.verdict.glyph + " ", ha="left", va="top", color=colour, **style
        )
        tail = Annotation(
            fmt_effect(m), xy=(1, 0), xycoords=anchor, ha="left", va="bottom", color=t.ink, **style
        )
    page.fig.add_artist(tail)


# --------------------------------------------------------------------------------------
# Marks.


def _dot_size(n: int) -> float:
    """Marker diameter (pt) for a column of *n* samples: big when few, small when many."""
    for limit, size in ((8, 15.0), (20, 11.0), (50, 8.5), (120, 6.5), (300, 4.8)):
        if n <= limit:
            return size
    return 3.2


_VIOLIN_N = 300


def _beeswarm(y_in: np.ndarray, d_in: float, half_in: float) -> np.ndarray:
    """Deterministic beeswarm: x offsets (in) so dots of diameter *d_in* do not overlap.

    Points are placed from the lowest value up, each at the smallest |x| that clears
    every dot already placed; a swarm wider than ±*half_in* is squeezed to fit.
    """
    n = len(y_in)
    xs = np.zeros(n)
    order = np.argsort(y_in, kind="stable")
    placed: list[int] = []
    d2 = d_in * d_in
    for i in order:
        near = [j for j in placed if abs(y_in[i] - y_in[j]) < d_in]
        cands = [0.0]
        for j in near:
            dx = math.sqrt(max(d2 - (y_in[i] - y_in[j]) ** 2, 0.0))
            cands += [xs[j] + dx, xs[j] - dx]
        cands.sort(key=lambda v: (round(abs(v), 9), v))
        for cx in cands:
            if all((cx - xs[j]) ** 2 + (y_in[i] - y_in[j]) ** 2 >= d2 * 0.999 for j in near):
                xs[i] = cx
                break
        placed.append(i)
    widest = float(np.abs(xs).max()) if n else 0.0
    if widest > half_in > 0:
        xs *= half_in / widest
    return xs


def _swarm_columns(
    columns: Sequence[np.ndarray], size: float, y_scale: float, half_in: float
) -> tuple[float, list[np.ndarray]]:
    """Dot size (pt) and x offsets (in) for each column; dots shrink until the swarms fit."""
    floor = min(size, 4.5)
    while True:
        d_in = size / 72.0 * 1.06
        offsets, widest = [], 0.0
        for vals in columns:
            off = np.full(len(vals), np.nan)
            ok = np.isfinite(vals)
            off[ok] = _beeswarm(vals[ok] * y_scale, d_in, math.inf)
            widest = max(widest, float(np.nanmax(np.abs(off))) if ok.any() else 0.0)
            offsets.append(off)
        if widest <= half_in or size <= floor:
            if widest > half_in:
                offsets = [off * half_in / widest for off in offsets]
            return size, offsets
        size = max(floor, size * 0.85)


def _kde(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Gaussian kernel density with Scott's bandwidth (numpy only)."""
    v = values[np.isfinite(values)]
    sd = v.std(ddof=1) if len(v) > 1 else 0.0
    iqr = np.subtract(*np.percentile(v, [75, 25])) / 1.349 if len(v) > 1 else 0.0
    spread = min(sd, iqr) if iqr > 0 else sd
    bw = 1.06 * (spread if spread > 0 else max(abs(v.mean()) * 0.01, 1e-9)) * len(v) ** -0.2
    z = (grid[:, None] - v[None, :]) / bw
    return np.exp(-0.5 * z * z).sum(axis=1) / (len(v) * bw * math.sqrt(2 * math.pi))


def _delta(m: MetricEvidence) -> float:
    return math.log1p(m.margin) if m.kind == "positive" else m.margin


def _to_data(m: MetricEvidence, anchor: float, value: float) -> float:
    """An effect-scale value as a metric value: the base median moved by *value*."""
    return anchor * math.exp(value) if m.kind == "positive" else anchor + value


_MIN_CI_IN = 0.12  # 12 px at the 800 px display width


def _ci_marks(
    ax: Axes,
    pos: float,
    lows: tuple[float, float],
    highs: tuple[float, float],
    estimate: float,
    colour: str,
    theme: Theme,
    *,
    vertical: bool = True,
    hollow: bool = False,
    thick: float = 7.0,
    size: float = 7.5,
    show95: bool = True,
    per_in: float | None = None,
    cap: float = 0.0,
) -> None:
    """An interval at *pos*: thin 95 % line (only when wider), rounded decision bar, end caps, point.

    *lows*/*highs* are (decision, 95 %) ends, already on the axis's scale. *per_in* is
    the axis's data units per inch: with it, an interval shorter than 12 px at display
    is drawn at that length (centred on the estimate) and the rounded bar ends are
    pulled in so the bar's ink ends at the CI ends. *cap* is the end caps' half-width in
    the other axis's data units (0: no caps).
    """
    lo90, hi90, lo95, hi95 = lows[0], highs[0], lows[1], highs[1]
    if per_in is not None:
        least = _MIN_CI_IN * per_in
        if hi90 - lo90 < least:
            lo90, hi90 = estimate - least / 2, estimate + least / 2
        lo95, hi95 = min(lo95, lo90), max(hi95, hi90)
    outer = (lo95, hi95) if show95 and (lo95 < lo90 or hi95 > hi90) else (lo90, hi90)

    def line(a: float, b: float, lw: float, capstyle: str) -> None:
        xy = ([pos, pos], [a, b]) if vertical else ([a, b], [pos, pos])
        ax.plot(*xy, color=colour, lw=lw, solid_capstyle=capstyle, zorder=6)

    if outer != (lo90, hi90):
        line(*outer, 2.0, "butt")
    inset = 0.0 if per_in is None else min(thick / 2 / 72 * per_in, (hi90 - lo90) / 2 * 0.9)
    line(lo90 + inset, hi90 - inset, thick, "round" if per_in is not None else "butt")
    if cap > 0:
        for end in outer:
            xy = (
                ([pos - cap, pos + cap], [end, end])
                if vertical
                else ([end, end], [pos - cap, pos + cap])
            )
            ax.plot(*xy, color=colour, lw=2.0, solid_capstyle="butt", zorder=6)
    pt = ([pos], [estimate]) if vertical else ([estimate], [pos])
    ax.plot(
        *pt,
        marker="o",
        markersize=size,
        markerfacecolor=theme.surface if hollow else colour,
        markeredgecolor=colour if hollow else theme.surface,
        markeredgewidth=1.6,
        linestyle="",
        zorder=7,
    )


def _effect_ci(m: MetricEvidence, fn: Callable[[float], float] = float) -> dict:
    e = m.effect
    return {
        "lows": (fn(e.ci.low), fn(e.ci95.low)),
        "highs": (fn(e.ci.high), fn(e.ci95.high)),
        "estimate": fn(e.estimate),
        "show95": e.ci95.level > e.ci.level,
    }


def _unit_formatter(units: str) -> Any:
    from matplotlib.ticker import FuncFormatter

    suffix = f" {units}" if units else ""
    return FuncFormatter(lambda v, _pos: f"{v:g}{suffix}")


def _value_ticks(ax: Axes, units: str, *, axis: str = "y", nbins: int = 4) -> None:
    from matplotlib.ticker import MaxNLocator

    target = ax.yaxis if axis == "y" else ax.xaxis
    target.set_major_locator(MaxNLocator(nbins=nbins, min_n_ticks=3))
    target.set_major_formatter(_unit_formatter(units))


def _nice_step(span: float) -> float:
    """A 1/2/2.5/5 × 10^k tick step that puts about four ticks across *span*."""
    raw = span / 4.0
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            return mult * mag
    return 10 * mag


def effect_limits(metrics: Sequence[MetricEvidence], pad: float = 0.12) -> tuple[float, float]:
    """Symmetric effect-axis limits that hold every 95 % CI and every margin."""
    reach = 0.0
    for m in metrics:
        reach = max(reach, abs(m.effect.ci95.low), abs(m.effect.ci95.high), _delta(m))
    reach = reach * (1 + pad) if reach > 0 else 0.1
    return -reach, reach


def _effect_axis(
    ax: Axes, m: MetricEvidence, lim: tuple[float, float], theme: Theme, *, vertical: bool
) -> None:
    """The effect axis: limits, % (or pp) ticks, the 0 line and the ±Δ band."""
    delta = _delta(m)
    (ax.axhspan if vertical else ax.axvspan)(-delta, delta, color=theme.band, zorder=0, lw=0)
    (ax.axhline if vertical else ax.axvline)(0, color=theme.muted, linewidth=1.0, zorder=1)
    (ax.set_ylim if vertical else ax.set_xlim)(*lim)
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


def _ring(theme: Theme, size: float) -> dict:
    return {"markeredgecolor": theme.surface, "markeredgewidth": 1.0 if size >= 6 else 0.4}  # noqa: PLR2004


# --------------------------------------------------------------------------------------
# The arms panel: every sample of both arms, the margin band and the CI bracket.

_CI_X = 1.78  # the bracket's column, right of the candidate column (at 1)


def _arm_limits(m: MetricEvidence, *, ci: bool) -> tuple[float, float, float]:
    b, c = m.base[np.isfinite(m.base)], m.cand[np.isfinite(m.cand)]
    anchor = float(np.median(b))
    delta = _delta(m)
    vals = [*b, *c, _to_data(m, anchor, -delta), _to_data(m, anchor, delta)]
    if ci:
        vals += [_to_data(m, anchor, m.effect.ci95.low), _to_data(m, anchor, m.effect.ci95.high)]
    lo, hi = min(vals), max(vals)
    pad = 0.08 * (hi - lo or abs(anchor) * 0.1 or 1.0)
    return lo - pad, hi + pad, anchor


def _arms(
    ax: Axes,
    m: MetricEvidence,
    theme: Theme,
    w_in: float,
    h_in: float,
    *,
    ci: bool = True,
    label_size: float = _LABEL,
) -> None:
    """Draw both arms of continuous *m* into *ax* (w_in × h_in inches)."""
    t = theme
    b, c = m.base, m.cand
    lo, hi, anchor = _arm_limits(m, ci=ci)
    xlim = (-0.6, _CI_X + 0.38) if ci else (-0.6, 1.6)
    ax.set_xlim(*xlim)
    ax.set_ylim(lo, hi)
    x_scale = w_in / (xlim[1] - xlim[0])
    y_scale = h_in / (hi - lo)
    n = max(np.isfinite(b).sum(), np.isfinite(c).sum())
    size, offsets = _swarm_columns((b, c), _dot_size(int(n)), y_scale, 0.36 * x_scale)
    offsets = [off / x_scale for off in offsets]
    # The margin: ±Δ around the base median, under both columns and the bracket.
    band_lo, band_hi = _to_data(m, anchor, -_delta(m)), _to_data(m, anchor, _delta(m))
    ax.fill_between([-0.5, xlim[1] - 0.06], band_lo, band_hi, color=t.band, lw=0, zorder=0)
    ax.grid(axis="y", color=t.grid, linewidth=0.8, zorder=-1)
    ax.set_axisbelow(True)
    if m.paired and len(b) == len(c):
        for xb, vb, xc, vc in zip(offsets[0], b, offsets[1], c, strict=True):
            if not (np.isfinite(vb) and np.isfinite(vc)):
                continue
            better = (vc - vb) * m.sign > 0
            ax.plot(
                [xb, 1 + xc],
                [vb, vc],
                color=t.better if better else t.worse,
                alpha=0.4,
                lw=1.1,
                zorder=2,
            )
    for x, vals, off, colour in ((0, b, offsets[0], t.base), (1, c, offsets[1], t.cand)):
        ok = np.isfinite(vals)
        if ok.sum() > _VIOLIN_N:
            grid = np.linspace(lo, hi, 300)
            dens = _kde(vals[ok], grid)
            dens = dens / dens.max() * 0.42
            side = -1 if x == 0 else 1
            ax.fill_betweenx(grid, x, x + side * dens, color=colour, alpha=0.16, lw=0, zorder=1)
        ax.plot(
            x + off[ok],
            vals[ok],
            "o",
            color=colour,
            markersize=size,
            alpha=0.85 if ok.sum() > _VIOLIN_N else 1.0,
            zorder=3,
            linestyle="",
            **_ring(t, size),
        )
        med = float(np.median(vals[ok]))
        ax.plot(
            [x - 0.3, x + 0.3], [med, med], color=t.ink, lw=4.0, solid_capstyle="butt", zorder=5
        )
    if ci:
        colour = t.verdict_colour(m.verdict.kind)
        _ci_marks(
            ax,
            _CI_X,
            colour=colour,
            theme=t,
            hollow=not m.fdr_pass,
            thick=6.0,
            size=5.5,
            per_in=1 / y_scale,
            cap=0.07,
            **_effect_ci(m, lambda v: _to_data(m, anchor, v)),
        )
    ax.set_xticks(
        [0, 1],
        [f"base\nn={int(np.isfinite(b).sum())}", f"candidate\nn={int(np.isfinite(c).sum())}"],
    )
    ax.tick_params(axis="x", labelsize=label_size, colors=t.ink, pad=6)
    _value_ticks(ax, m.units)


def _mini_waffles(ax: Axes, m: MetricEvidence, theme: Theme, w_in: float, h_in: float) -> None:
    """Both arms of binary *m* as two small waffles side by side (canvas in inches)."""
    e = m.effect
    if not isinstance(e, ProportionEffect):
        raise TypeError("_mini_waffles needs a binary metric")
    label_h = 0.55
    half = w_in / 2
    nmax = max(e.n_base, e.n_cand)
    cols = max(2, math.ceil(math.sqrt(nmax * 1.5)))
    rows = math.ceil(nmax / cols)
    cell = min(0.24, (half * 0.82) / cols, (h_in - label_h - 0.1) / rows)
    good_is_one = m.direction == "maximize"
    for arm, (k, n, colour) in enumerate(
        ((e.k_base, e.n_base, theme.base), (e.k_cand, e.n_cand, theme.cand))
    ):
        x0 = arm * half + (half - cols * cell) / 2
        y_top = h_in - 0.05
        _waffle(ax, k, n, cols, cell, x0, y_top, colour, theme, good_is_one=good_is_one)
        ax.text(
            arm * half + half / 2,
            y_top - rows * cell - 0.1,
            f"{'base' if arm == 0 else 'candidate'}\nn={n}",
            ha="center",
            va="top",
            fontsize=_LABEL,
            color=theme.ink,
            linespacing=1.15,
        )


def _waffle(
    ax: Axes,
    k: int,
    n: int,
    cols: int,
    cell: float,
    x0: float,
    y_top: float,
    colour: str,
    theme: Theme,
    *,
    good_is_one: bool,
) -> None:
    """One square per run, filled row by row from the top-left; a bad outcome is a crossed square."""
    from matplotlib.patches import FancyBboxPatch

    gap = max(cell * 0.12, 0.02)
    outcomes = [1] * k + [0] * (n - k)
    if not good_is_one:
        outcomes = outcomes[::-1]
    for idx, out in enumerate(outcomes):
        r, cc = divmod(idx, cols)
        x = x0 + cc * cell
        y = y_top - (r + 1) * cell
        good = (out == 1) == good_is_one
        ax.add_patch(
            FancyBboxPatch(
                (x + gap / 2, y + gap / 2),
                cell - gap,
                cell - gap,
                boxstyle=f"round,pad=0,rounding_size={cell * 0.14}",
                facecolor=colour if good else theme.worse,
                edgecolor="none",
            )
        )
        if not good:
            inset = cell * 0.3
            for ys in ((y + inset, y + cell - inset), (y + cell - inset, y + inset)):
                ax.plot(
                    [x + inset, x + cell - inset],
                    list(ys),
                    color=theme.surface,
                    lw=max(1.2, cell * 9),
                    solid_capstyle="round",
                )


# --------------------------------------------------------------------------------------
# The run order: one row of squares per shard, in execution order.

_SQ_MAX = 0.15
_SQ_MIN = 0.045
_VM_LABEL_IN = 0.62


def _order_lines(runs: Sequence[_Run], width_in: float) -> list[tuple[int | None, list[_Run]]]:
    shards = sorted({r.shard for r in runs}, key=str) if any(r.shard for r in runs) else [None]
    label_w = _VM_LABEL_IN if shards != [None] else 0.0
    per_line = max(1, int((width_in - label_w) / _SQ_MIN))
    lines: list[tuple[int | None, list[_Run]]] = []
    for k, s in enumerate(shards):
        mine = sorted((r for r in runs if r.shard == s), key=lambda r: r.order or 0.0)
        lines.extend(
            ((k if s is not None else None) if i == 0 else None, mine[i : i + per_line])
            for i in range(0, len(mine), per_line)
        )
    return lines


def _order_height(cells: Sequence[MetricEvidence], width_in: float) -> float:
    if not order_recorded(cells):
        return 0.0
    lines = _order_lines(_runs(cells), width_in)
    labelled = any(s is not None for s, _ in lines)
    longest = max(len(v) for _, v in lines)
    label_w = _VM_LABEL_IN if labelled else 0.0
    pitch = min(_SQ_MAX, (width_in - label_w) / max(longest, 1))
    row = max(pitch, 0.24 if labelled else pitch)
    return 0.32 + len(lines) * row


def _draw_order(
    page: _Page, cells: Sequence[MetricEvidence], top: float, x0: float, width_in: float
) -> None:
    """The run-order rows at *top*: grey base, blue candidate squares; "VM k" per shard."""
    height = _order_height(cells, width_in)
    if height <= 0:
        return
    t = page.theme
    ax = page.canvas(x0, top, width_in, height)
    lines = _order_lines(_runs(cells), width_in)
    labelled = any(s is not None for s, _ in lines)
    label_w = _VM_LABEL_IN if labelled else 0.0
    longest = max(len(v) for _, v in lines)
    pitch = min(_SQ_MAX, (width_in - label_w) / max(longest, 1))
    row = max(pitch, 0.24 if labelled else pitch)
    ax.plot([0, width_in], [height - 0.1, height - 0.1], color=t.grid, lw=0.8)
    for j, (shard, line) in enumerate(lines):
        y = height - 0.32 - (j + 1) * row + (row - pitch) / 2
        if shard is not None:
            ax.text(
                0,
                y + pitch / 2,
                f"VM {shard + 1}",
                ha="left",
                va="center",
                fontsize=_MIN_PT,
                color=t.ink2,
            )
        gap = pitch * 0.2
        for i, r in enumerate(line):
            ax.add_patch(
                _rect(
                    (label_w + i * pitch + gap / 2, y + gap / 2),
                    pitch - gap,
                    pitch - gap,
                    t.base if r.arm == 0 else t.cand,
                )
            )


def _rect(xy: tuple[float, float], w: float, h: float, colour: str) -> Any:
    from matplotlib.patches import Rectangle

    return Rectangle(xy, w, h, facecolor=colour, edgecolor="none")


# --------------------------------------------------------------------------------------
# G1 Scorecard: small multiples, one panel per primary metric.


def draw_scorecard(
    metrics: Sequence[MetricEvidence],
    theme: Theme = LIGHT,
    *,
    title: str | None = None,
    per_row: int = 4,
) -> Figure:
    """G1: one panel per metric: name, big effect + glyph, every sample, Δ band, CI bracket."""
    import matplotlib as mpl

    with mpl.rc_context(_rc()):
        n = len(metrics)
        cols = max(1, min(per_row, n))
        rows = math.ceil(n / cols)
        usable = WIDTH_IN - 2 * _SIDE_IN
        gutter = 0.3
        panel_w = min(5.0 if cols == 1 else 3.7, (usable - gutter * (cols - 1)) / cols)
        x_start = (WIDTH_IN - (cols * panel_w + gutter * (cols - 1))) / 2
        binary_only = all(isinstance(m.effect, ProportionEffect) for m in metrics)
        name_h = 0.34 if n > 1 else 0.0
        hero_h, label_h = 0.62, 0.62
        plot_h = 1.0 if binary_only else 2.5 if cols < 4 else 2.2  # noqa: PLR2004
        row_h = name_h + hero_h + plot_h + label_h + 0.2
        order_h = _order_height(metrics[:1], usable)
        page = _Page(_HEAD_IN + rows * row_h + order_h + _FOOT_IN, theme)
        page.header(title or short_summary(metrics))
        hero_size = _HERO if cols <= 2 else 23  # noqa: PLR2004
        for i, m in enumerate(metrics):
            r, c = divmod(i, cols)
            px = x_start + c * (panel_w + gutter)
            top = _HEAD_IN + r * row_h
            if name_h:
                page.text(
                    px,
                    top,
                    humanize(m.name),
                    ha="left",
                    va="top",
                    fontsize=_LABEL,
                    color=theme.ink2,
                )
            _hero(page, px, top + name_h, m, ha="left", size=hero_size)
            ptop = top + name_h + hero_h
            if isinstance(m.effect, ProportionEffect):
                ax = page.canvas(px, ptop, panel_w, plot_h + label_h)
                _mini_waffles(ax, m, theme, panel_w, plot_h + label_h)
            else:
                tick_w = 0.72
                ax = page.axes(px + tick_w, ptop, panel_w - tick_w, plot_h)
                _arms(ax, m, theme, panel_w - tick_w, plot_h)
        _draw_order(page, metrics[:1], _HEAD_IN + rows * row_h, _SIDE_IN, usable)
        return page.fig


# --------------------------------------------------------------------------------------
# G2 Forest plot.


def draw_forest(
    metrics: Sequence[MetricEvidence],
    theme: Theme = LIGHT,
    *,
    title: str | None = None,
    labels: Sequence[str] | None = None,
) -> Figure:
    """G2: one row per metric or sweep point, sorted by effect, on the shared axis.

    Each row: the name, a dot strip of both arms' samples (on the row's own scale),
    the point with its decision (thick) and 95 % (thin) CI over the ±Δ band, and the
    verdict glyph. A row that fails the FDR check is hollow; a primary metric is bold.
    """
    import matplotlib as mpl

    with mpl.rc_context(_rc()):
        t = theme
        names = list(labels) if labels is not None else [humanize(m.name) for m in metrics]
        order = sorted(range(len(metrics)), key=lambda i: metrics[i].effect.estimate)
        n = len(metrics)
        row_h = 0.56
        axis_h = 0.5
        order_h = _order_height(metrics[:1], WIDTH_IN - 2 * _SIDE_IN)
        page = _Page(_HEAD_IN + n * row_h + axis_h + order_h + _FOOT_IN, theme)
        if title is None:
            moved = sum(
                m.verdict.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED) for m in metrics
            )
            same = sum(m.verdict.kind == VerdictKind.EQUIVALENT for m in metrics)
            title = f"All {n} unchanged" if same == n else f"{moved} of {n} moved"
        page.header(title)
        name_w, strip_x, strip_w, ax_x, ax_w = 2.15, 2.6, 1.55, 4.45, 2.75
        ax = page.axes(ax_x, _HEAD_IN, ax_w, n * row_h)
        ax.set_ylim(-0.5, n - 0.5)
        ax.set_yticks([])
        _effect_axis(ax, metrics[0], effect_limits(metrics), t, vertical=False)
        for row, i in enumerate(reversed(order)):
            m = metrics[i]
            y = n - 1 - row
            colour = t.verdict_colour(m.verdict.kind)
            _ci_marks(
                ax,
                y,
                colour=colour,
                theme=t,
                vertical=False,
                hollow=not m.fdr_pass,
                thick=6.0,
                size=10.0,
                **_effect_ci(m),
            )
            top = _HEAD_IN + row * row_h
            page.text(
                _SIDE_IN + name_w,
                top + row_h / 2,
                names[i],
                ha="right",
                va="center",
                fontsize=_LABEL,
                color=t.ink,
                weight="bold" if m.primary else "normal",
            )
            page.text(
                ax_x + ax_w + 0.25,
                top + row_h / 2,
                m.verdict.glyph,
                ha="left",
                va="center",
                fontsize=_LABEL + 3,
                color=colour,
                weight="bold",
            )
            if isinstance(m.effect, Effect):
                _dot_strip(
                    page.canvas(strip_x, top + 0.06, strip_w, row_h - 0.12),
                    m,
                    t,
                    strip_w,
                    row_h - 0.12,
                )
        _draw_order(
            page, metrics[:1], _HEAD_IN + n * row_h + axis_h, _SIDE_IN, WIDTH_IN - 2 * _SIDE_IN
        )
        return page.fig


def _dot_strip(ax: Axes, m: MetricEvidence, theme: Theme, w_in: float, h_in: float) -> None:
    """Both arms' samples as two thin dot rows (base above, candidate below), own scale."""
    b, c = m.base[np.isfinite(m.base)], m.cand[np.isfinite(m.cand)]
    both = np.concatenate([b, c])
    lo, hi = float(both.min()), float(both.max())
    span = hi - lo or 1.0

    def x_of(v: np.ndarray) -> np.ndarray:
        return 0.05 + (v - lo) / span * (w_in - 0.1)

    ax.plot([0, w_in], [h_in / 2, h_in / 2], color=theme.grid, lw=0.8, zorder=0)
    for vals, colour, y in ((b, theme.base, h_in * 0.72), (c, theme.cand, h_in * 0.28)):
        ax.plot(
            x_of(vals),
            np.full(len(vals), y),
            "o",
            color=colour,
            markersize=5.0,
            alpha=0.75,
            markeredgewidth=0,
        )
        med = float(np.median(vals))
        ax.plot([x_of(np.array([med]))[0]] * 2, [y - 0.1, y + 0.1], color=theme.ink, lw=2.4)


# --------------------------------------------------------------------------------------
# G3 Estimation plot.


def draw_estimation(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G3: both arms (every sample, Δ band, CI bracket) and the bootstrap distribution of the effect."""
    import matplotlib as mpl

    if not isinstance(m.effect, Effect):
        raise TypeError("draw_estimation needs a continuous metric")
    e = m.effect
    with mpl.rc_context(_rc()):
        t = theme
        plot_h = 3.3
        order_h = _order_height([m], WIDTH_IN - 2 * _SIDE_IN)
        page = _Page(_HEAD_IN + plot_h + 0.75 + order_h + _FOOT_IN, theme)
        page.header(title or chart_title(m), m)
        ax = page.axes(1.05, _HEAD_IN + 0.1, 4.25, plot_h)
        _arms(ax, m, t, 4.25, plot_h)
        # The effect's bootstrap distribution, on the effect axis.
        ex = page.axes(5.85, _HEAD_IN + 0.1, 1.15, plot_h)
        lim = effect_limits([m], pad=0.25)
        if e.bootstrap is not None:
            lo, hi = np.percentile(e.bootstrap, [0.1, 99.9])
            lim = (min(lim[0], lo), max(lim[1], hi))
        _effect_axis(ex, m, lim, t, vertical=True)
        ex.yaxis.tick_right()
        ex.set_xlim(-0.35, 1.1)
        ex.set_xticks([])
        colour = t.verdict_colour(m.verdict.kind)
        if e.bootstrap is not None:
            grid = np.linspace(lim[0], lim[1], 300)
            dens = _kde(e.bootstrap, grid)
            dens = dens / dens.max() * 0.85
            ex.fill_betweenx(grid, 0.12, 0.12 + dens, color=colour, alpha=0.22, lw=0, zorder=2)
            outline = np.where(dens > _DENSITY_FLOOR, 0.12 + dens, np.nan)
            ex.plot(outline, grid, color=colour, lw=1.2, alpha=0.8, zorder=2)
        _ci_marks(
            ex,
            0.0,
            colour=colour,
            theme=t,
            hollow=not m.fdr_pass,
            per_in=(lim[1] - lim[0]) / plot_h,
            cap=0.1,
            **_effect_ci(m),
        )
        _draw_order(page, [m], _HEAD_IN + plot_h + 0.75, _SIDE_IN, WIDTH_IN - 2 * _SIDE_IN)
        return page.fig


# --------------------------------------------------------------------------------------
# G4 Raincloud + shift function.


def draw_raincloud_shift(
    m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None
) -> Figure:
    """G4: per arm a half-violin, a box and every sample; under it the decile shift function."""
    import matplotlib as mpl

    scale = "log" if m.kind == "positive" else "diff"
    sf = shift_function(m.base, m.cand, scale=scale, paired=m.paired)
    with mpl.rc_context(_rc()):
        t = theme
        page = _Page(6.4, theme)
        page.header(title or _shift_title(sf, m), m)
        cloud_w, cloud_h = 5.95, 2.6
        ax = page.axes(1.7, _HEAD_IN + 0.1, cloud_w, cloud_h)
        ax.set_yticks([])
        b, c = m.base[np.isfinite(m.base)], m.cand[np.isfinite(m.cand)]
        both = np.concatenate([b, c])
        lo, hi = float(both.min()), float(both.max())
        pad = 0.05 * (hi - lo or 1.0)
        grid = np.linspace(lo - pad, hi + pad, 400)
        ax.set_xlim(grid[0], grid[-1])
        ax.set_ylim(-0.42, 1.72)
        x_scale = cloud_w / (grid[-1] - grid[0])
        y_scale = cloud_h / (1.72 + 0.42)
        size = min(_dot_size(max(len(b), len(c))), 7.5)
        ax.grid(axis="x", color=t.grid, linewidth=0.8)
        ax.set_axisbelow(True)
        for row, (vals, colour, name) in enumerate(((c, t.cand, "candidate"), (b, t.base, "base"))):
            y0 = row * 1.0
            dens = _kde(vals, grid)
            dens = dens / dens.max() * 0.55
            ax.fill_between(grid, y0 + 0.08, y0 + 0.08 + dens, color=colour, alpha=0.25, lw=0)
            ax.plot(grid, y0 + 0.08 + dens, color=colour, lw=1.4)
            q1, med, q3 = np.percentile(vals, [25, 50, 75])
            ax.plot([q1, q3], [y0, y0], color=t.ink, lw=3.5, solid_capstyle="butt", zorder=4)
            ax.plot(
                [med],
                [y0],
                marker="o",
                markersize=8,
                color=t.surface,
                markeredgecolor=t.ink,
                markeredgewidth=2.0,
                zorder=5,
            )
            off = _beeswarm(vals * x_scale, size / 72 * 1.05, 0.13 * y_scale) / y_scale
            ax.plot(
                vals,
                y0 - 0.22 + off,
                "o",
                color=colour,
                markersize=size,
                linestyle="",
                zorder=3,
                **_ring(t, size),
            )
            page.text(
                1.55,
                _HEAD_IN + 0.1 + (1.72 - (y0 + 0.05)) * cloud_h / 2.14,
                f"{name}\nn={len(vals)}",
                ha="right",
                va="center",
                fontsize=_LABEL,
                color=t.ink,
                linespacing=1.15,
            )
        _value_ticks(ax, m.units, axis="x", nbins=5)
        # Shift function.
        sx = page.axes(1.7, _HEAD_IN + cloud_h + 0.7, cloud_w, 1.9)
        sx.grid(axis="y", color=t.grid, linewidth=0.8)
        x = np.arange(len(sf.probs))
        lim = (min(sf.low.min(), -_delta(m)) * 1.15, max(sf.high.max(), _delta(m)) * 1.15)
        _effect_axis(sx, m, lim, t, vertical=True)
        sx.plot(x, sf.diff, color=t.muted, lw=1.2, zorder=2)
        for i in range(len(x)):
            excl = sf.low[i] > 0 or sf.high[i] < 0
            good = sf.diff[i] * m.sign > 0
            colour = (t.better if good else t.worse) if excl else t.muted
            sx.plot(
                [x[i], x[i]],
                [sf.low[i], sf.high[i]],
                color=colour,
                lw=3.0,
                solid_capstyle="butt",
                zorder=3,
            )
            sx.plot(
                [x[i]],
                [sf.diff[i]],
                "o",
                color=colour,
                markersize=10,
                markeredgecolor=t.surface,
                markeredgewidth=1.8,
                zorder=4,
            )
        sx.set_xticks(x, [f"q{i + 1}" for i in range(len(x))])
        sx.tick_params(axis="x", labelsize=_LABEL, colors=t.ink)
        sx.set_xlim(-0.5, len(x) - 0.5)
        return page.fig


def _shift_title(sf: ShiftFunction, m: MetricEvidence) -> str:
    """``Median +1 %, q9 +52 %``."""
    i_med = sf.probs.index(0.5)
    tail = len(sf.probs) - 1
    unit = unit_suffix(m)
    med, top = display(m, sf.diff[i_med]), display(m, sf.diff[tail])
    return f"Median {fmt_signed(med, 0)}{unit}, q{tail + 1} {fmt_signed(top, 0)}{unit}"


def shift_summary(m: MetricEvidence) -> str:
    """The shift function in words for the Markdown: every decile's change and 95 % CI."""
    scale = "log" if m.kind == "positive" else "diff"
    sf = shift_function(m.base, m.cand, scale=scale, paired=m.paired)
    unit = unit_suffix(m)
    parts = [
        f"q{i + 1} {fmt_signed(display(m, d), 0)} [{fmt_signed(display(m, lo), 0)} … {fmt_signed(display(m, hi), 0)}]"
        for i, (d, lo, hi) in enumerate(zip(sf.diff, sf.low, sf.high, strict=True))
    ]
    return ", ".join(parts) + unit


# --------------------------------------------------------------------------------------
# G5 Waffle.


def _waffle_columns(n: int) -> int:
    """Squares per waffle row: one row up to 20 runs, then about two rows, wider past 30 and 60."""
    for limit, cols in ((60, 20), (30, 15)):
        if n > limit:
            return cols
    one_row = 20
    return n if n <= one_row else max(10, math.ceil(n / 2))


def worst_plausible(m: MetricEvidence) -> float | None:
    """For a candidate with no bad outcome: the difference at the 95 % upper bound of its bad rate."""
    e = m.effect
    if not isinstance(e, ProportionEffect):
        return None
    good_is_one = m.direction == "maximize"
    bad = e.n_cand - e.k_cand if good_is_one else e.k_cand
    if bad != 0:
        return None
    return (1 - e.bad_upper) - e.p_base if good_is_one else e.bad_upper - e.p_base


def draw_waffle(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G5: one square per run per arm; the difference CI over the ±Δ band; the zero-failure bound."""
    import matplotlib as mpl

    e = m.effect
    if not isinstance(e, ProportionEffect):
        raise TypeError("draw_waffle needs a binary metric")
    with mpl.rc_context(_rc()):
        t = theme
        nmax = max(e.n_base, e.n_cand)
        cols = _waffle_columns(nmax)
        grid_x = 1.75
        cell = min(0.32, (WIDTH_IN - _SIDE_IN - grid_x) / cols)
        blocks = [
            ("base", e.k_base, e.n_base, t.base),
            ("candidate", e.k_cand, e.n_cand, t.cand),
        ]
        heights = [math.ceil(n / cols) * cell + 0.25 for _, _, n, _ in blocks]
        diff_h = 0.75
        order_h = _order_height([m], WIDTH_IN - 2 * _SIDE_IN)
        page = _Page(
            _HEAD_IN + 0.15 + sum(heights) + 0.15 + diff_h + 0.6 + order_h + _FOOT_IN, theme
        )
        page.header(title or chart_title(m), m)
        top = _HEAD_IN + 0.15
        good_is_one = m.direction == "maximize"
        for (arm, k, n, colour), bh in zip(blocks, heights, strict=True):
            ax = page.canvas(grid_x, top, cols * cell + 0.05, bh)
            _waffle(ax, k, n, cols, cell, 0, bh - 0.05, colour, t, good_is_one=good_is_one)
            rows = math.ceil(n / cols)
            page.text(
                grid_x - 0.2,
                top + 0.05 + rows * cell / 2,
                f"{arm}\nn={n}",
                ha="right",
                va="center",
                fontsize=_LABEL,
                color=t.ink,
                linespacing=1.15,
            )
            top += bh
        # The difference: one bar over the ±Δ band, with the zero-failure bound as a tick.
        dx = page.axes(grid_x, top + 0.15, WIDTH_IN - _SIDE_IN - grid_x - 0.1, diff_h)
        dx.set_yticks([])
        dx.set_ylim(-1, 1)
        lim = effect_limits([m], pad=0.2)
        bound = worst_plausible(m)
        if bound is not None:
            reach = max(abs(lim[0]), abs(bound) * 1.15)
            lim = (-reach, reach)
        _effect_axis(dx, m, lim, t, vertical=False)
        colour = t.verdict_colour(m.verdict.kind)
        _ci_marks(
            dx, 0, colour=colour, theme=t, vertical=False, thick=9.0, size=13.0, **_effect_ci(m)
        )
        if bound is not None:
            dx.plot(
                [bound, bound], [-0.75, 0.75], color=t.ink, lw=2.6, zorder=8, solid_capstyle="butt"
            )
        _draw_order(page, [m], top + 0.15 + diff_h + 0.6, _SIDE_IN, WIDTH_IN - 2 * _SIDE_IN)
        return page.fig


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
    """G6: top, both arms' samples at each point with lines joining the medians; bottom, the effect.

    The points sit at even steps in sweep order; the tick labels give the values.
    """
    import matplotlib as mpl

    with mpl.rc_context(_rc()):
        t = theme
        m0 = cells[0]
        top_h, eff_h = 2.7, 1.75
        order_h = _order_height(cells, WIDTH_IN - 2 * _SIDE_IN)
        page = _Page(_HEAD_IN + 0.1 + top_h + 0.25 + eff_h + 0.55 + order_h + _FOOT_IN, theme)
        moved = sum(m.verdict.kind in (VerdictKind.IMPROVED, VerdictKind.REGRESSED) for m in cells)
        page.header(title or f"{moved} of {len(cells)} {x_name} points moved")
        x = np.arange(len(cells), dtype=float)
        plot_x, plot_w = 1.2, WIDTH_IN - 1.2 - 1.3
        ax = page.axes(plot_x, _HEAD_IN + 0.1, plot_w, top_h)
        xlim = (-0.6, len(cells) - 0.4)
        ax.set_xlim(*xlim)
        vals_all = np.concatenate([np.concatenate([m.base, m.cand]) for m in cells])
        vals_all = vals_all[np.isfinite(vals_all)]
        lo, hi = float(vals_all.min()), float(vals_all.max())
        pad = 0.06 * (hi - lo or 1.0)
        ax.set_ylim(lo - pad, hi + pad)
        ax.grid(axis="y", color=t.grid, linewidth=0.8)
        ax.set_axisbelow(True)
        x_scale = plot_w / (xlim[1] - xlim[0])
        y_scale = top_h / (hi - lo + 2 * pad)
        n = max(max(len(m.base), len(m.cand)) for m in cells)
        size = min(_dot_size(n), 6.0 if len(cells) > 4 else 8.0)  # noqa: PLR2004
        half = 0.17
        for arm, colour, side in (("base", t.base, -0.21), ("cand", t.cand, 0.21)):
            meds = []
            for xi, m in zip(x, cells, strict=True):
                vals = getattr(m, arm)
                vals = vals[np.isfinite(vals)]
                off = _beeswarm(vals * y_scale, size / 72 * 1.04, half * 0.5 * x_scale) / x_scale
                ax.plot(
                    xi + side + off,
                    vals,
                    "o",
                    color=colour,
                    markersize=size,
                    linestyle="",
                    zorder=3,
                    **_ring(t, size),
                )
                meds.append(float(np.median(vals)))
            ax.plot(x + side, meds, color=colour, lw=2.4, zorder=4, solid_capstyle="round")
            ax.text(
                x[-1] + side + 0.32,
                meds[-1],
                "base" if arm == "base" else "candidate",
                ha="left",
                va="center",
                fontsize=_LABEL,
                color=t.ink,
            )
        ax.set_xticks(x, [])
        _value_ticks(ax, m0.units)
        ex = page.axes(plot_x, _HEAD_IN + 0.1 + top_h + 0.25, plot_w, eff_h)
        lim = effect_limits(cells, pad=0.3)
        _effect_axis(ex, m0, lim, t, vertical=True)
        ex.grid(axis="y", color=t.grid, linewidth=0.6)
        for xi, m in zip(x, cells, strict=True):
            colour = t.verdict_colour(m.verdict.kind)
            _ci_marks(
                ex,
                xi,
                colour=colour,
                theme=t,
                hollow=not m.fdr_pass,
                per_in=(lim[1] - lim[0]) / eff_h,
                cap=0.1,
                **_effect_ci(m),
            )
            ex.text(
                xi,
                max(m.effect.ci.high, m.effect.ci95.high) + 0.04 * (lim[1] - lim[0]),
                m.verdict.glyph,
                ha="center",
                va="bottom",
                fontsize=_LABEL + 1,
                color=colour,
                weight="bold",
                zorder=8,
            )
        ex.set_xlim(*xlim)
        ex.set_xticks(x, [f"{v:g}" for v in xs])
        ex.tick_params(axis="x", labelsize=_LABEL, colors=t.ink)
        _draw_order(
            page,
            cells,
            _HEAD_IN + 0.1 + top_h + 0.25 + eff_h + 0.55,
            _SIDE_IN,
            WIDTH_IN - 2 * _SIDE_IN,
        )
        return page.fig


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

    Each cell carries its glyph and its effect rounded to a whole number; a cell whose
    CI crosses the margin (inconclusive) is hatched. ``cells[j][i]`` is the cell at
    ``ys[j]``, ``xs[i]``.
    """
    import matplotlib as mpl
    from matplotlib.colors import LinearSegmentedColormap, to_rgb
    from matplotlib.patches import Rectangle

    with mpl.rc_context(_rc()):
        t = theme
        ny, nx = len(ys), len(xs)
        cell_w = min(1.25, 4.9 / nx)
        cell_h = min(0.8, cell_w * 0.75)
        flat = [m for row in cells for m in row]
        order_h = _order_height(flat, WIDTH_IN - 2 * _SIDE_IN)
        grid_h = ny * cell_h
        page = _Page(_HEAD_IN + 0.15 + grid_h + 0.85 + order_h + _FOOT_IN, theme)
        m0 = flat[0]
        n_better = sum(m.verdict.kind == VerdictKind.IMPROVED for m in flat)
        n_worse = sum(m.verdict.kind == VerdictKind.REGRESSED for m in flat)
        page.header(title or f"{n_better} better, {n_worse} worse of {len(flat)}")
        oriented = np.array([[m.sign * m.effect.estimate for m in row] for row in cells])
        reach = max(float(np.abs(oriented).max()), _delta(m0)) or 1.0
        cmap = LinearSegmentedColormap.from_list("bo", [t.worse, t.mid, t.cand])
        gx = 1.55
        ax = page.axes(gx, _HEAD_IN + 0.15, nx * cell_w, grid_h)
        ax.tick_params(colors=t.ink, labelsize=_LABEL, length=0)
        for j, row in enumerate(cells):
            for i, m in enumerate(row):
                rgb = to_rgb(cmap(0.5 + 0.5 * oriented[j, i] / reach))
                ax.add_patch(
                    Rectangle((i + 0.03, j + 0.04), 0.94, 0.92, facecolor=rgb, edgecolor="none")
                )
                if m.verdict.kind == VerdictKind.INCONCLUSIVE:
                    ax.add_patch(
                        Rectangle(
                            (i + 0.03, j + 0.04),
                            0.94,
                            0.92,
                            facecolor="none",
                            edgecolor=t.surface,
                            hatch="////",
                            lw=0,
                        )
                    )
                lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
                ink = "#111111" if lum > 0.55 else "#ffffff"  # noqa: PLR2004
                pct = display(m, m.effect.estimate)
                ax.text(
                    i + 0.5,
                    j + 0.5,
                    f"{m.verdict.glyph} {fmt_signed(pct, 0)}{unit_suffix(m).strip()}",
                    ha="center",
                    va="center",
                    fontsize=_LABEL,
                    color=ink,
                    weight="bold",
                )
        ax.set_xlim(0, nx)
        ax.set_ylim(0, ny)
        ax.set_xticks(np.arange(nx) + 0.5, [str(v) for v in xs])
        ax.set_yticks(np.arange(ny) + 0.5, [str(v) for v in ys])
        ax.set_xlabel(x_name, fontsize=_LABEL, color=t.ink2)
        ax.set_ylabel(y_name, fontsize=_LABEL, color=t.ink2)
        # The key: the ramp (▲ at the better end) and one hatched swatch for "?".
        kx_x = gx + nx * cell_w + 0.45
        kx = page.axes(kx_x, _HEAD_IN + 0.15, 0.22, grid_h * 0.72)
        kx.imshow(
            np.linspace(1, 0, 256)[:, None], aspect="auto", cmap=cmap, extent=(0, 1, -reach, reach)
        )
        kx.set_xticks([])
        kx.yaxis.tick_right()
        ticks = [-reach, 0, reach]
        kx.set_yticks(
            ticks,
            [
                "▼ " + fmt_signed(display(m0, -reach * m0.sign), 0) + unit_suffix(m0),
                "0",
                "▲ " + fmt_signed(display(m0, reach * m0.sign), 0) + unit_suffix(m0),
            ],
        )
        kx.tick_params(colors=t.ink2, labelsize=_TICK, length=0)
        sw = page.axes(kx_x, _HEAD_IN + 0.15 + grid_h * 0.72 + 0.18, 0.22, 0.22)
        sw.set_xlim(0, 1)
        sw.set_ylim(0, 1)
        sw.set_xticks([])
        sw.set_yticks([])
        sw.add_patch(Rectangle((0, 0), 1, 1, facecolor=t.mid, edgecolor="none"))
        sw.add_patch(
            Rectangle((0, 0), 1, 1, facecolor="none", edgecolor=t.ink2, hatch="////", lw=0)
        )
        page.text(
            kx_x + 0.32,
            _HEAD_IN + 0.15 + grid_h * 0.72 + 0.29,
            "?",
            ha="left",
            va="center",
            fontsize=_LABEL + 1,
            color=t.unsure,
            weight="bold",
        )
        _draw_order(page, flat, _HEAD_IN + 0.15 + grid_h + 0.85, _SIDE_IN, WIDTH_IN - 2 * _SIDE_IN)
        return page.fig


# --------------------------------------------------------------------------------------
# G8 Power bar.


def draw_power(m: MetricEvidence, theme: Theme = LIGHT, *, title: str | None = None) -> Figure:
    """G8: the minimum detectable effect against the margin, and the runs that would close the gap."""
    import matplotlib as mpl

    v = m.verdict
    if v.mde is None:
        raise ValueError("draw_power needs a verdict with an MDE")
    with mpl.rc_context(_rc()):
        t = theme
        page = _Page(2.6, theme)
        mde_d = abs(display(m, v.mde))
        delta_d = abs(display(m, v.margin))
        unit = unit_suffix(m)
        add = v.add_runs
        if title is None:
            title = f"Add ~{add} runs per arm" if add else "Power is enough"
        page.header(title)
        if v.runs_needed:
            page.text(
                WIDTH_IN - _SIDE_IN,
                0.16,
                f"n {v.n} → {v.runs_needed}",
                ha="right",
                va="top",
                fontsize=_HERO,
                weight="bold",
                color=t.ink,
            )
        ax = page.axes(_SIDE_IN + 0.75, _HEAD_IN + 0.45, 5.6, 0.55)
        ax.set_yticks([])
        reach = max(mde_d, delta_d) * 1.3
        ax.set_xlim(0, reach)
        ax.set_ylim(-1, 1)
        ax.barh([0], [mde_d], height=1.2, color=t.unsure if v.underpowered else t.better)
        ax.plot([delta_d, delta_d], [-1.15, 1.15], color=t.ink, lw=2.4, clip_on=False)
        ax.text(
            delta_d,
            1.3,
            "Δ",
            ha="center",
            va="bottom",
            fontsize=_LABEL + 2,
            color=t.ink,
            weight="bold",
        )
        page.text(
            _SIDE_IN + 0.65,
            _HEAD_IN + 0.45 + 0.275,
            "MDE",
            ha="right",
            va="center",
            fontsize=_LABEL,
            color=t.ink,
        )
        _value_ticks(ax, unit.strip(), axis="x", nbins=5)
        return page.fig


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
        t = theme
        page = _Page(3.9, theme)
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
                else f"Drift of {fmt_signed(worst, 0)} % in one arm"
            )
        page.header(title)
        ax = page.axes(1.15, _HEAD_IN + 0.1, 5.4, 2.5)
        ax.grid(axis="y", color=t.grid, linewidth=0.8)
        ax.set_axisbelow(True)
        if aa_band is not None and np.isfinite(b).any():
            med = float(np.nanmedian(b))
            lo, hi = (
                (med * (1 + aa_band[0]), med * (1 + aa_band[1]))
                if m.kind == "positive"
                else (med + aa_band[0], med + aa_band[1])
            )
            ax.axhspan(lo, hi, color=t.band, lw=0, zorder=0)
            ax.text(
                1.0,
                hi,
                " A/A",
                transform=ax.get_yaxis_transform(),
                fontsize=_LABEL,
                color=t.ink2,
                va="bottom",
            )
        for (vals, order, colour, name, cl), sl in zip(
            (
                (b, order_base, t.base, "base", m.clusters[0]),
                (c, order_cand, t.cand, "candidate", m.clusters[0] if m.paired else m.clusters[1]),
            ),
            slopes,
            strict=True,
        ):
            xo = np.asarray(order, dtype=float)
            groups = (
                [(None, np.ones(len(vals), dtype=bool))]
                if cl is None
                else [(k, cl == lab) for k, lab in enumerate(dict.fromkeys(cl.tolist()))]
            )
            for k, sel in groups:
                ax.plot(
                    xo[sel],
                    vals[sel],
                    shard_markers[(k or 0) % len(shard_markers)],
                    color=colour,
                    markersize=7,
                    linestyle="",
                    zorder=3,
                    **_ring(t, 7),
                )
            if sl is not None:
                slope, icpt, xs_, _ = sl
                ax.plot(
                    [xs_.min(), xs_.max()],
                    [icpt + slope * xs_.min(), icpt + slope * xs_.max()],
                    color=colour,
                    lw=2.4,
                    zorder=4,
                )
                ax.text(
                    xs_.max(),
                    icpt + slope * xs_.max(),
                    f"  {name}",
                    ha="left",
                    va="center",
                    fontsize=_LABEL,
                    color=t.ink,
                )
        _value_ticks(ax, m.units)
        from matplotlib.ticker import MaxNLocator

        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
        return page.fig


# --------------------------------------------------------------------------------------
# Saving.


def save_both(draw: Callable[[Theme], Figure], out_dir: str | Path, stem: str) -> dict[str, Path]:
    """Draw *draw(theme)* in both themes; write ``{stem}-{light,dark}.{png,svg}`` to *out_dir*.

    Returns ``{"light": png, "dark": png, "light_svg": svg, "dark_svg": svg}``.
    """
    import matplotlib as mpl

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for theme in THEMES:
        with mpl.rc_context(_rc()):
            fig = draw(theme)
            png = out / f"{stem}-{theme.name}.png"
            svg = out / f"{stem}-{theme.name}.svg"
            fig.savefig(png, dpi=DPI, facecolor=theme.surface)
            fig.savefig(svg, facecolor=theme.surface, metadata={"Date": None})
        paths[theme.name] = png
        paths[f"{theme.name}_svg"] = svg
    return paths
