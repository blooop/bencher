"""Write the dash-flow demo plates as standalone SVG files.

The data are synthetic and seeded, so every run writes the same files. The script uses
only the standard library:

    python docs/evidence_dash_flow/make_svgs.py           # write the plates
    python docs/evidence_dash_flow/make_svgs.py --check   # check the motion rule

The style is the one of #1188: every sample is a dot, the margin is a grey band on the
metric's own axis, and text is a short finding, one effect number with its verdict glyph,
and axis labels. The charts carry no interval mark: the glyph (▲ ▼ ≈ ?) gives the verdict of
the CI test, the big number gives the effect, and the dots show the spread and n. The 90 %
CI goes in the alt text and in the caption under each image.

The motion rule: dots, bars, medians, bands, text and glyphs never move, resize, fade or
glow. The only motion is dashes that flow along secondary lines, made with
stroke-dashoffset on a dashed stroke. Every frame is the complete still chart, and
``prefers-reduced-motion`` stops all flow.

The salience rule: only three kinds of line flow. The median connector of a ▲▼ panel (base
median to candidate median: the size of the change), the forest connector of a ▲▼ row (0
to the estimate), and the outline of the runs that failed or changed outcome. Pair lines
are still.

``--check`` parses every SVG's CSS and fails if anything else animates, if an animated
element is not one of those three kinds, or if a likely-range band, a CI bar, a capped
interval, a whisker or a leader is left in a plate. ``--captions`` prints the CI line of
each plate for the PR body.
"""

# ruff: noqa: PLR2004, RUF001
# PLR2004: a plot is mostly literal coordinates. RUF001: the labels use the real minus
# sign, the approximately-equal sign and arrows on purpose.

from __future__ import annotations

import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import NormalDist
from typing import TYPE_CHECKING, NamedTuple
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from collections.abc import Callable

OUT = Path(__file__).resolve().parent
W = 800
FS = 15  # smallest text, in px at the 800 px display width
MASK = 0xFFFFFFFF

SANS = '-apple-system,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif'
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# Okabe-Ito marks. The t* tokens are text steps of the same hues, dark enough to read as
# text on white; on the dark surface the mark colours already pass.
LIGHT = {
    "plate": "#FFFFFF",
    "ink": "#16191D",
    "ink2": "#4A515B",
    "muted": "#69717B",
    "rule": "#E2E5EA",
    "grid": "#ECEEF2",
    "base": "#8C8C8C",
    "cand": "#0072B2",
    "better": "#009E73",
    "worse": "#D55E00",
    "unsure": "#E69F00",
    "tbetter": "#007A59",
    "tworse": "#B34A00",
    "tunsure": "#9A6700",
    "band": "#E3EDF7",
    "bandEdge": "#9DB8D3",
    "chip": "#EEF1F5",
    "white": "#FFFFFF",
}
DARK = {
    "plate": "#0D1117",
    "ink": "#E6EDF3",
    "ink2": "#B1BAC4",
    "muted": "#8B949E",
    "rule": "#30363D",
    "grid": "#21262D",
    "base": "#9A9A9A",
    "cand": "#3D9BD6",
    "better": "#1FA07C",
    "worse": "#E0662A",
    "unsure": "#BE8714",
    "tbetter": "#2DB98F",
    "tworse": "#EC7A43",
    "tunsure": "#D39B2A",
    "band": "#1A2836",
    "bandEdge": "#3F5F80",
    "chip": "#1C2128",
    "white": "#FFFFFF",
}

# verdict kind -> (mark token, text token, glyph shape)
VERDICT = {
    "improved": ("better", "tbetter", "up"),
    "regressed": ("worse", "tworse", "down"),
    "equiv": ("ink2", "ink2", "≈"),
    "small": ("ink2", "ink2", "≈"),
    "unsure": ("unsure", "tunsure", "?"),
}

# ---------------------------------------------------------------- numbers and data


def _i32(x: int) -> int:
    x &= MASK
    return x - (1 << 32) if x >= 1 << 31 else x


class XorShift:
    """The 32-bit xorshift of the HTML design page, so both show the same numbers."""

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def rnd(self) -> float:
        s = _i32(self.seed ^ _i32((self.seed & MASK) << 13))
        s = _i32(s ^ ((s & MASK) >> 17))
        s = _i32(s ^ _i32((s & MASK) << 5))
        self.seed = s
        return ((s & MASK) % 1_000_000_000) / 1e9

    def norm(self) -> float:
        u = 0.0
        while not u:
            u = self.rnd()
        v = 0.0
        while not v:
            v = self.rnd()
        return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


def quant(a: list[float], p: float) -> float:
    s = sorted(a)
    i = (len(s) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def mean(a: list[float]) -> float:
    return sum(a) / len(a)


def sd(a: list[float]) -> float:
    m = mean(a)
    return math.sqrt(sum((x - m) ** 2 for x in a) / (len(a) - 1))


def pct(log_ratio: float) -> float:
    return (math.exp(log_ratio) - 1) * 100


def fmt(v: float, d: int = 1) -> str:
    sign = "+" if v > 0 else "−" if v < 0 else ""
    return f"{sign}{abs(v):.{d}f}"


def verdict(lo: float, hi: float, d: float) -> str:
    """Return the verdict for a CI [lo, hi] oriented so that positive is better."""
    if lo > 0 and hi > d:
        return "improved"
    if hi < 0 and lo < -d:
        return "regressed"
    if lo > -d and hi < d:
        return "small" if (lo > 0 or hi < 0) else "equiv"
    return "unsure"


def t_ci(log_diffs: list[float], t: float) -> tuple[float, float, float]:
    """Return the mean log difference and its t interval."""
    m = mean(log_diffs)
    h = t * sd(log_diffs) / math.sqrt(len(log_diffs))
    return m, m - h, m + h


Z = NormalDist()
Z90 = Z.inv_cdf(0.95)  # two-sided 90 %
Z80 = Z.inv_cdf(0.80)  # 80 % power


def bca(xs: list[float], boots: list[float], level: float = 0.90) -> tuple[float, float]:
    """Return the BCa bootstrap interval of the mean of xs."""
    est = mean(xs)
    z0 = Z.inv_cdf(sum(b < est for b in boots) / len(boots))
    jack = [(sum(xs) - x) / (len(xs) - 1) for x in xs]
    jm = mean(jack)
    num_ = sum((jm - j) ** 3 for j in jack)
    den = 6 * sum((jm - j) ** 2 for j in jack) ** 1.5
    acc = num_ / den
    out = []
    for q in ((1 - level) / 2, (1 + level) / 2):
        zq = Z.inv_cdf(q)
        out.append(quant(boots, Z.cdf(z0 + (z0 + zq) / (1 - acc * (z0 + zq)))))
    return out[0], out[1]


def wilson(k: int, n: int, z: float = Z90) -> tuple[float, float]:
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z / (1 + z * z / n) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return c - h, c + h


def newcombe(k1: int, n1: int, k2: int, n2: int, z: float = Z90) -> tuple[float, float]:
    """Return the Newcombe hybrid-score interval of p2 - p1."""
    p1, p2 = k1 / n1, k2 / n2
    (l1, u1), (l2, u2) = wilson(k1, n1, z), wilson(k2, n2, z)
    d = p2 - p1
    return (
        d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2),
        d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2),
    )


def zero_fail_bound(n: int, alpha: float = 0.05) -> float:
    """Return the exact one-sided upper bound on a rate after 0 events in n runs."""
    return 1 - alpha ** (1 / n)


def runs_for_bound(bound: float, alpha: float = 0.05) -> int:
    return math.ceil(math.log(alpha) / math.log(1 - bound))


class Pair(NamedTuple):
    shard: int
    idx: int
    base: float
    cand: float
    order: str


def _boot(rng: XorShift, xs: list[float], n: int = 4000) -> list[float]:
    out = []
    for _ in range(n):
        acc = 0.0
        for _j in range(len(xs)):
            acc += xs[math.floor(rng.rnd() * len(xs))]
        out.append(acc / len(xs))
    return out


RNG = XorShift(20261019)
SHARD_SPEED = [1.0, 1.12, 0.94, 1.05]
PAIRS: list[Pair] = []
for _s in range(4):
    for _p in range(5):
        _scen = math.exp(0.18 * RNG.norm())
        _b = 0.42 * SHARD_SPEED[_s] * _scen * math.exp(0.05 * RNG.norm())
        _c = _b * math.exp(math.log(0.816) + 0.07 * RNG.norm())
        PAIRS.append(Pair(_s, _p, _b, _c, "BA" if _p % 2 else "AB"))
LOG_DIFF = [math.log(p.cand / p.base) for p in PAIRS]
BOOTS = _boot(RNG, LOG_DIFF)
EST = mean(LOG_DIFF)
C90 = bca(LOG_DIFF, BOOTS)
MARGIN = math.log(1.05)

# tracking_error_rms: a second paired metric on the same runs, with no real change
_TR = XorShift(31)
TRACK: list[Pair] = []
for _s in range(4):
    for _p in range(5):
        _b = 12.0 * SHARD_SPEED[_s] * math.exp(0.10 * _TR.norm())
        _c = _b * math.exp(math.log(1.004) + 0.03 * _TR.norm())
        TRACK.append(Pair(_s, _p, _b, _c, "BA" if _p % 2 else "AB"))
TRACK_LD = [math.log(p.cand / p.base) for p in TRACK]
TRACK_BOOTS = _boot(_TR, TRACK_LD)
TRACK_EST = mean(TRACK_LD)
TRACK_C90 = bca(TRACK_LD, TRACK_BOOTS)

# task_success counts passes, required_sigkill counts kills, each out of n runs
TS_BASE, TS_CAND, TS_N = 17, 18, 18
TS_DIFF = (TS_CAND - TS_BASE) / TS_N
TS_CI = newcombe(TS_BASE, TS_N, TS_CAND, TS_N)
SK_BASE, SK_CAND, SK_N = 4, 0, 30
SK_BOUND = zero_fail_bound(SK_N)
SK_RUNS = {b: runs_for_bound(b) for b in (0.05, 0.01)}

TS_KIND = verdict(TS_CI[0], TS_CI[1], 0.05)  # ±5 pp margin
TS_TXT = f"{fmt(TS_DIFF * 100)} pp"
TS_CI_TXT = f"[{fmt(TS_CI[0] * 100)}, {fmt(TS_CI[1] * 100)}] pp"


# ---------------------------------------------------------------- SVG primitives


def num(v: object) -> str:
    if isinstance(v, float):
        s = f"{v:.2f}".rstrip("0").rstrip(".")
        return "0" if s == "-0" else s
    return escape(str(v), {'"': "&quot;"})


def el(tag: str, body: str | None = None, **attrs: object) -> str:
    parts = [tag]
    for key, val in attrs.items():
        if val is None:
            continue
        name = "class" if key == "cls" else key.rstrip("_").replace("_", "-")
        parts.append(f'{name}="{num(val)}"')
    head = " ".join(parts)
    return f"<{head}/>" if body is None else f"<{head}>{body}</{tag}>"


def text(
    x: float,
    y: float,
    s: str,
    cls: str = "f-ink2",
    size: float = FS,
    anchor: str | None = None,
    **attrs: object,
) -> str:
    return el("text", escape(s), x=x, y=y, cls=cls, font_size=size, text_anchor=anchor, **attrs)


def line(
    x1: float, y1: float, x2: float, y2: float, cls: str, width: float = 1, **attrs: object
) -> str:
    return el("line", x1=x1, y1=y1, x2=x2, y2=y2, cls=cls, stroke_width=width, **attrs)


def rect(x: float, y: float, w: float, h: float, cls: str, **attrs: object) -> str:
    return el("rect", x=x, y=y, width=w, height=h, cls=cls or None, **attrs)


def circle(cx: float, cy: float, r: float, cls: str, **attrs: object) -> str:
    return el("circle", cx=cx, cy=cy, r=r, cls=cls, **attrs)


def glyph(kind: str, x: float, y: float, size: float, cls: str = "") -> tuple[str, float]:
    """Draw the verdict glyph of kind with its left edge at x on baseline y.

    Return the SVG and the glyph's width. The triangles are paths, so they do not depend
    on a font that has U+25B2 and U+25BC.
    """
    _, tok, shape = VERDICT[kind]
    if shape in {"up", "down"}:
        w, h = size * 0.74, size * 0.66
        if shape == "up":
            bot = y - size * 0.02
            d = f"M{num(x)} {num(bot)}L{num(x + w / 2)} {num(bot - h)}L{num(x + w)} {num(bot)}Z"
        else:
            top = y - size * 0.7
            d = f"M{num(x)} {num(top)}L{num(x + w)} {num(top)}L{num(x + w / 2)} {num(top + h)}Z"
        return el("path", d=d, cls=f"f-{tok} {cls}".strip()), w
    return text(x, y, shape, f"f-{tok} bb {cls}".strip(), size), size * 0.62


def nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    t, out = math.ceil(lo / step) * step, []
    while t <= hi + 1e-9:
        out.append(round(t, 10))
        t += step
    return out


def swarm(pos: list[float], r: float, *, one_sided: bool = False) -> list[float]:
    """Return offsets that place dots of radius r at pos without overlap (a beeswarm)."""
    d = 2 * r + 0.8
    out = [0.0] * len(pos)
    placed: list[tuple[float, float]] = []
    for i in sorted(range(len(pos)), key=lambda i: pos[i]):
        p = pos[i]
        near = [(q, o) for q, o in placed if abs(q - p) < d]
        cands = [0.0]
        for q, o in near:
            dx = math.sqrt(d * d - (q - p) ** 2)
            cands += [o + dx, o - dx]
        if one_sided:
            cands = [c for c in cands if c >= 0]
        ok = [c for c in cands if all((c - o) ** 2 + (p - q) ** 2 >= d * d - 1e-6 for q, o in near)]
        best = min(ok, key=abs) if ok else max((o for _, o in near), default=0) + d
        out[i] = best
        placed.append((p, best))
    return out


def legend(right: float, y: float, items: list[tuple[str, str]]) -> str:
    """Draw colour swatches with labels, right-aligned at right."""
    out, x = [], right
    for cls, name in reversed(items):
        x -= len(name) * FS * 0.55
        out.append(text(x, y, name, "f-ink2"))
        x -= 19
        out.append(rect(x, y - 11, 13, 13, cls, rx=2))
        x -= 18
    return "".join(out)


# ---------------------------------------------------------------- flow


class Look(NamedTuple):
    """How a flowing line looks: speed in px/s, dash and gap in px, stroke opacity."""

    code: str
    speed: float
    dash: float
    gap: float
    opacity: float

    @property
    def name(self) -> str:
        return "fl-" + self.code.lower().replace(".", "_")

    def css(self) -> str:
        """Return the keyframes and the class. Only stroke-dashoffset moves."""
        cycle = self.dash + self.gap
        travel = cycle * math.ceil(24 / cycle)  # whole cycles, so the loop has no seam
        return (
            f"@keyframes k{self.name}{{to{{stroke-dashoffset:-{num(float(travel))}}}}}"
            f".{self.name}{{stroke-dasharray:{num(float(self.dash))} {num(float(self.gap))};"
            f"animation:k{self.name} {travel / self.speed:.2f}s linear infinite}}"
        )


# S: speed. 6 s, 3 s and 1.5 s for 24 px of travel. #1188's liked drift was 6 px/s.
SPEEDS = {"S1": ("slow", 4.0), "S2": ("medium", 8.0), "S3": ("fast", 16.0)}
# P: dash pattern, dash and gap in px
PATTERNS = {
    "P1": ("dots 1-3", 1.0, 3.0),
    "P2": ("dash 4-4", 4.0, 4.0),
    "P3": ("dash 8-6", 8.0, 6.0),
}
# C: the stroke opacity of the flowing median connector
CONTRASTS = {"C1": 0.35, "C2": 0.6, "C3": 0.9}
DEFAULT = Look("S2P2C2", 8.0, 4.0, 4.0, 0.6)
FLOW = Look("flow", 8.0, 4.0, 4.0, 1.0)  # the median connector and the run outline

BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
.dash{{stroke-dasharray:4 4}}
"""
REDUCED = "\n@media (prefers-reduced-motion:reduce){.fl{animation:none!important}}\n"


ARMS = [("f-base", "base"), ("f-cand", "candidate")]
FOOT = 26  # the strip under each plate that carries its code


class Plate:
    def __init__(
        self,
        title: str,
        height: float,
        desc: str,
        big: tuple[str, str] | None = None,
        code: str = "",
    ) -> None:
        self.title, self.height, self.desc, self.big, self.code = title, height, desc, big, code
        self.parts: list[str] = []
        self.looks: dict[str, Look] = {}
        self.legend = False

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def flow(self, look: Look) -> str:
        """Return the classes of a line that flows with look."""
        self.looks[look.name] = look
        return f"fl {look.name}"

    @staticmethod
    def _palette(pal: dict[str, str]) -> str:
        return "".join(f".f-{k}{{fill:{v}}}.s-{k}{{stroke:{v}}}" for k, v in pal.items())

    def render(self) -> str:
        total = self.height + FOOT
        h = num(float(total))
        css = (
            BASE_CSS
            + "".join(lk.css() for lk in self.looks.values())
            + self._palette(LIGHT)
            + "\n@media (prefers-color-scheme:dark){"
            + self._palette(DARK)
            + "}"
            + REDUCED
        )
        head = [
            rect(0.5, 0.5, W - 1, total - 1, "f-plate s-rule", rx=6),
            text(20, 40, self.title, "f-ink bb", 23),
            text(20, total - 12, self.code, "mono f-muted"),
        ]
        if self.big:
            kind, s = self.big
            gw = 30 * 0.74
            g, _ = glyph(kind, W - 20 - gw, 42, 30)
            head += [g, text(W - 30 - gw, 42, s, "f-ink bb", 30, "end")]
        elif self.legend:
            head.append(legend(W - 20, 38, ARMS))
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{''.join(head)}{''.join(self.parts)}</svg>\n"
        )


# ---------------------------------------------------------------- change axes


MOVED = {"improved", "regressed"}
SAME = {"equiv", "small"}


def kind_of(ci: tuple[float, float], *, lower_better: bool, d: float = MARGIN) -> str:
    a, b = ci
    return verdict(-b, -a, d) if lower_better else verdict(a, b, d)


def ci_pct(ci: tuple[float, float]) -> str:
    """Return a log-ratio CI as a percent range for a caption."""
    return f"[{fmt(pct(ci[0]))}, {fmt(pct(ci[1]))}] %"


def h_axis(
    xs: Callable[[float], float],
    y0: float,
    y1: float,
    d: float,
    ticks: list[tuple[float, str]],
    label_y: float,
) -> str:
    """Draw a horizontal change axis: the ±d band, the 0 line and the ticks."""
    out = [rect(xs(-d), y0, xs(d) - xs(-d), y1 - y0, "f-band s-bandEdge", stroke_width=1)]
    for v, lab in ticks:
        if v:
            out.append(line(xs(v), y0, xs(v), y1, "s-grid"))
        out.append(text(xs(v), label_y, lab, "mono f-muted", FS, "middle"))
    out.append(line(xs(0), y0, xs(0), y1, "s-muted", 1.5))
    return "".join(out)


def est_mark(
    xs: Callable[[float], float],
    y: float,
    est: float,
    kind: str,
    pl: Plate | None = None,
) -> str:
    """Draw an estimate on a horizontal change axis as a dot in the verdict colour.

    With pl, a connector runs from 0 to the estimate: on a ▲▼ row it flows toward the
    estimate, on a ? row it is drawn still and dashed, and a ≈ row has none.
    """
    mark = VERDICT[kind][0]
    out = []
    if pl is not None and kind in MOVED:
        out.append(line(xs(0), y, xs(est), y, f"s-{mark} estflow {pl.flow(FLOW)}", 2.5))
    elif pl is not None and kind == "unsure":
        out.append(line(xs(0), y, xs(est), y, f"s-{mark} dash", 2, stroke_opacity=0.6))
    out.append(circle(xs(est), y, 5, f"f-{mark} s-plate", stroke_width=1.5))
    return "".join(out)


# ---------------------------------------------------------------- shared marks


def _side_labels(
    x: float, room: float, items: list[tuple[float, str, str, str]], y_min: float, y_max: float
) -> str:
    """Write each (y, label, class, place) at x, on one line if room allows, else on two.

    place is "mid" (centred on y), "above" (ends just above y) or "below" (starts just
    below y). Labels that would touch are pushed apart.
    """
    one_line = all(len(s) * FS * 0.55 <= room for _, s, _, _ in items)
    rows = [[s] if one_line else s.rsplit(" ", 1) for _, s, _, _ in items]
    hs = [len(r) * (FS + 2) for r in rows]
    want = []
    for (y, _, _, place), h in zip(items, hs, strict=True):
        want.append({"mid": y - h / 2, "above": y - h - 3, "below": y + 3}[place])
    order = sorted(range(len(items)), key=lambda i: want[i])
    tops: dict[int, float] = {}
    edge = y_min
    for i in order:
        tops[i] = max(want[i], edge)
        edge = tops[i] + hs[i] + 4
    over = edge - 4 - y_max
    if over > 0:
        for i in tops:
            tops[i] -= over
    out = []
    for i, (_, _, cls, _) in enumerate(items):
        for k, part in enumerate(rows[i]):
            out.append(text(x, tops[i] + FS - 2 + k * (FS + 2), part, cls, FS))
    return "".join(out)


def dot_panel(
    pl: Plate,
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    base: list[float],
    cand: list[float],
    lo: float,
    hi: float,
    ci: tuple[float, float],
    lower_better: bool = True,
    ticks: list[float] | None = None,
    tick_fmt: Callable[[float], str] | None = None,
    tick_labels: bool = True,
    labels: str = "two",
    r: float = 4.5,
    margin_label: bool = False,
    connector: bool = False,
    look: Look = FLOW,
) -> str:
    """Draw base and candidate as beeswarm dot columns on the metric's own axis.

    The grey ±Δ band sits around the base median, and a thin line marks the base median:
    the 0 of the shift. There is no interval mark: ci only sets the verdict colour.
    margin_label writes "±5 % margin" beside the grey band. connector draws an upright
    line from the base median level to the candidate median level, in the gap between
    the columns; it flows on a ▲▼ panel and is still on ≈ and ?.
    """
    out = []

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    kind = kind_of(ci, lower_better=lower_better)
    px = x0 + (48 if tick_labels else 0)
    wid = x1 - px
    cb, cc = (px + wid * 0.2, px + wid * 0.5) if margin_label else (px + wid * 0.27, px + wid * 0.6)
    for t in ticks or []:
        out.append(line(px, ys(t), x1, ys(t), "s-grid"))
        if tick_labels and tick_fmt:
            out.append(text(px - 7, ys(t) + 5, tick_fmt(t), "mono f-muted", FS, "end"))
    bmed, cmed = quant(base, 0.5), quant(cand, 0.5)

    def yv(v: float) -> float:  # a shift v (log ratio), placed against the base median
        return ys(bmed * math.exp(v))

    top, bot = yv(MARGIN), yv(-MARGIN)
    out.append(rect(px + 2, top, x1 - px - 4, bot - top, "f-band s-bandEdge", stroke_width=1))
    pb, pc = [ys(v) for v in base], [ys(v) for v in cand]
    ob, oc = swarm(pb, r), swarm(pc, r)
    mark, _, _ = VERDICT[kind]
    hws = [min(max(abs(o) for o in offs) + r + 5, wid * 0.15) for offs in (ob, oc)]
    out.append(line(cb + hws[0], yv(0), cc + hws[1] + 4, yv(0), "s-muted", 1.2))
    for i in range(len(base)):
        better = (cand[i] < base[i]) == lower_better
        tok = "cand" if better else "worse"
        xa, xb = cb + ob[i], cc + oc[i]
        out.append(
            line(xa, pb[i], xb, pc[i], f"s-{tok}", 1.2, stroke_opacity=0.3 if better else 0.6)
        )
    out += [
        circle(cb + o, p, r, "f-base s-plate", stroke_width=1) for o, p in zip(ob, pb, strict=True)
    ]
    out += [
        circle(cc + o, p, r, "f-cand s-plate", stroke_width=1) for o, p in zip(oc, pc, strict=True)
    ]
    if connector:  # base median level to candidate median level: the size of the change
        moved = kind in MOVED
        cls = f"s-{mark} medflow {pl.flow(look)}" if moved else f"s-{mark} dash"
        xm = (cb + hws[0] + cc - hws[1]) / 2  # upright, in the gap between the columns
        out.append(
            line(
                xm,
                ys(bmed),
                xm,
                ys(cmed),
                cls,
                2.5,
                stroke_opacity=look.opacity if moved else 0.5,
            )
        )
    for (cx, med, tok), hw in zip(((cb, bmed, "base"), (cc, cmed, "cand")), hws, strict=True):
        bar = line(cx - hw, ys(med), cx + hw, ys(med), "s-plate", 9, stroke_linecap="round")
        bar += line(cx - hw, ys(med), cx + hw, ys(med), f"s-{tok}", 5, stroke_linecap="round")
        out.append(bar)
    if margin_label:
        lx = cc + hws[1] + 12
        # the label sits outside the grey band, on the side away from the candidate median
        place = (bot, "below") if ys(cmed) < (top + bot) / 2 else (top, "above")
        out.append(
            _side_labels(
                lx,
                x1 - lx,
                [(place[0], f"±{pct(MARGIN):.0f} % margin", "f-muted", place[1])],
                y0,
                y1,
            )
        )
    if labels == "two":
        for cx, name, n in ((cb, "base", len(base)), (cc, "candidate", len(cand))):
            out += [
                text(cx, y1 + 26, name, "f-ink2", FS, "middle"),
                text(cx, y1 + 45, f"n={n}", "mono f-muted", FS, "middle"),
            ]
    elif labels == "n":
        for cx, n in ((cb, len(base)), (cc, len(cand))):
            out.append(text(cx, y1 + 26, f"n={n}", "mono f-muted", FS, "middle"))
    elif labels == "one":
        for cx, name, n in ((cb, "base", len(base)), (cc, "candidate", len(cand))):
            out.append(text(cx, y1 + 28, f"{name} n={n}", "f-ink2", FS, "middle"))
    return "".join(out)


class Strip(NamedTuple):
    """The geometry of a run-order strip: one thin row of squares per VM."""

    x0: float
    y0: float
    cell: float = 16
    h: float = 12
    gap: float = 3
    pair_gap: float = 6
    pitch: float = 22
    label_w: float = 58
    pairs: bool = True

    def x(self, i: int) -> float:
        return (
            self.x0
            + self.label_w
            + i * (self.cell + self.gap)
            + ((i // 2) * self.pair_gap if self.pairs else 0)
        )

    def y(self, row: int) -> float:
        return self.y0 + row * self.pitch


def run_rows(st: Strip, rows: list[tuple[str, str]]) -> str:
    """Draw the strip: "A" is base (grey), "B" candidate (blue). Nothing here moves."""
    out = []
    for r, (label, seq) in enumerate(rows):
        y = st.y(r)
        out.append(text(st.x0, y + st.h, label, "mono f-muted"))
        out += [
            rect(st.x(i), y, st.cell, st.h, "f-base" if a == "A" else "f-cand", rx=2)
            for i, a in enumerate(seq)
        ]
    return "".join(out)


def abba_rows(pairs: list[Pair]) -> list[tuple[str, str]]:
    return [(f"VM {s + 1}", "".join(p.order for p in pairs if p.shard == s)) for s in range(4)]


def axis_range(vals: list[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return lo - span * pad, hi + span * pad


def pct_ticks(lo: float, hi: float, n: int = 5) -> list[tuple[float, str]]:
    """Return (log ratio, label) ticks at nice whole percentages between lo and hi."""
    return [
        (math.log(1 + t / 100), "0" if t == 0 else f"{fmt(t, 0)} %")
        for t in nice_ticks(pct(lo), pct(hi), n)
    ]


def plan_kind() -> str:
    return kind_of(C90, lower_better=True)


def plan_title() -> str:
    return f"Planning is {abs(pct(EST)):.0f} % faster"


# startup_time: a third paired metric on the same runs, too noisy to decide
_UR = XorShift(89)
UNS: list[Pair] = []
for _s in range(4):
    for _p in range(5):
        _b = 1.6 * SHARD_SPEED[_s] * math.exp(0.08 * _UR.norm())
        _c = _b * math.exp(math.log(1.02) + 0.11 * _UR.norm())
        UNS.append(Pair(_s, _p, _b, _c, "BA" if _p % 2 else "AB"))
UNS_LD = [math.log(p.cand / p.base) for p in UNS]
UNS_EST = mean(UNS_LD)
UNS_C90 = bca(UNS_LD, _boot(_UR, UNS_LD))

# task_duration: a fourth paired metric on the same runs, 12 % slower on the candidate
_TD = XorShift(113)
DUR: list[Pair] = []
for _s in range(4):
    for _p in range(5):
        _b = 48.0 * SHARD_SPEED[_s] * math.exp(0.06 * _TD.norm())
        _c = _b * math.exp(math.log(1.12) + 0.05 * _TD.norm())
        DUR.append(Pair(_s, _p, _b, _c, "BA" if _p % 2 else "AB"))
DUR_LD = [math.log(p.cand / p.base) for p in DUR]
DUR_EST = mean(DUR_LD)
DUR_C90 = bca(DUR_LD, _boot(_TD, DUR_LD))

# the design plate: a metric with no real change, on VMs that slow down run by run
_DR = XorShift(77)
DRIFT = 0.008  # log slowdown per run on a VM
_TRUE = math.log(1.004)
DES: list[Pair] = []
for _s in range(4):
    _t = 0
    for _p in range(5):
        _o = "BA" if _p % 2 else "AB"
        _v = {}
        for _arm in _o:
            _v[_arm] = (
                12.0
                * SHARD_SPEED[_s]
                * math.exp(DRIFT * _t + 0.03 * _DR.norm() + (_TRUE if _arm == "B" else 0))
            )
            _t += 1
        DES.append(Pair(_s, _p, _v["A"], _v["B"], _o))
_m, _a, _b2 = t_ci([math.log(p.cand / p.base) for p in DES], 1.729)
DES_PAIRED = (_m, (_a, _b2))
_blk = [
    math.log(12.0 * math.exp(DRIFT * t + 0.03 * _DR.norm() + (_TRUE if t >= 10 else 0)))
    for t in range(20)
]
_d = mean(_blk[10:]) - mean(_blk[:10])
_h = 1.734 * math.sqrt(sd(_blk[:10]) ** 2 / 10 + sd(_blk[10:]) ** 2 / 10)
DES_BLOCKED = (_d, (_d - _h, _d + _h))


# ---------------------------------------------------------------- the decision plates


def _metric_panel(
    pl: Plate,
    x0: float,
    name: str,
    pairs: list[Pair],
    ci: tuple[float, float],
    est: float,
    *,
    margin_label: bool = False,
    width: float = 244,
    labels: str = "two",
) -> None:
    """Draw one paired metric: its name, its effect and glyph, and its dot panel."""
    kind = kind_of(ci, lower_better=True)
    big = f"{fmt(pct(est))} %"
    g, _ = glyph(kind, x0 + len(big) * 15.5 + 8, 116, 26)
    pl.add(text(x0, 80, name, "mono f-ink2"), text(x0, 116, big, "f-ink bb", 28), g)
    lo, hi = axis_range([p.base for p in pairs] + [p.cand for p in pairs])
    pl.add(
        dot_panel(
            pl,
            x0=x0,
            x1=x0 + width,
            y0=140,
            y1=360,
            base=[p.base for p in pairs],
            cand=[p.cand for p in pairs],
            lo=lo,
            hi=hi,
            ci=ci,
            ticks=nice_ticks(lo, hi),
            tick_fmt=lambda t: f"{t:g}",
            r=4,
            labels=labels,
            margin_label=margin_label,
            connector=True,
        )
    )


VERDICT_METRICS = (
    ("planning_time · s", PAIRS, C90, EST),
    ("task_duration · s", DUR, DUR_C90, DUR_EST),
    ("tracking_error · mm", TRACK, TRACK_C90, TRACK_EST),
    ("startup_time · s", UNS, UNS_C90, UNS_EST),
)
WORDS = {
    "improved": "improved",
    "regressed": "regressed",
    "equiv": "no change",
    "small": "no change",
    "unsure": "inconclusive",
}


def plate_verdicts(code: str) -> Plate:
    desc = "Four paired metrics, one per verdict, against the grey ±5 % margin band. " + "; ".join(
        f"{name.split(' ')[0]} {fmt(pct(est))} %, 90 % CI {ci_pct(ci)}, "
        f"{WORDS[kind_of(ci, lower_better=True)]}"
        for name, _, ci, est in VERDICT_METRICS
    )
    pl = Plate("Better, worse, same, unclear", 400, desc, code=code)
    pl.add(legend(W - 20, 38, [*ARMS, ("f-band s-bandEdge", "±5 % margin")]))
    for i, (name, pairs, ci, est) in enumerate(VERDICT_METRICS):
        _metric_panel(pl, 20 + i * 192, name, pairs, ci, est, width=180, labels="n")
    return pl


def _run_squares(
    pl: Plate,
    x0: float,
    y0: float,
    spec: tuple[int, int, str, int, float],
    changed: set[int],
    look: Look = FLOW,
) -> None:
    """Draw n runs as squares, a cross for each failure.

    The runs whose outcome differs from base get one flowing outline per row run of them:
    they are the runs that drive the binary result.
    """
    n, fails, tok, cols, c = spec
    g = c * 0.25
    for i in range(n):
        r, k = divmod(i, cols)
        x, y = x0 + k * (c + g), y0 + r * (c + g)
        if i >= n - fails:
            h = num(c / 2)
            cross = f"M{num(x + c * 0.25)} {num(y + c * 0.25)}l{h} {h}m0 -{h}l-{h} {h}"
            pl.add(
                rect(x, y, c, c, "f-plate s-worse", rx=3, stroke_width=2),
                el("path", d=cross, cls="s-worse", stroke_width=2),
            )
            continue
        pl.add(rect(x, y, c, c, f"f-{tok}", rx=3))
    runs: list[list[int]] = []
    for i in sorted(changed):
        if runs and runs[-1][-1] == i - 1 and i % cols:
            runs[-1].append(i)
        else:
            runs.append([i])
    for run in runs:
        r, k = divmod(run[0], cols)
        x, y = x0 + k * (c + g), y0 + r * (c + g)
        wide = len(run) * c + (len(run) - 1) * g
        pl.add(
            rect(
                x - 3.5,
                y - 3.5,
                wide + 7,
                c + 7,
                f"s-better runflag {pl.flow(look)}",
                rx=5,
                fill="none",
                stroke_width=2,
            )
        )


def plate_scorecard(code: str) -> Plate:
    k_dur = kind_of(DUR_C90, lower_better=True)
    desc = (
        f"planning_time {fmt(pct(EST))} % (90 % CI {ci_pct(C90)}), {WORDS[plan_kind()]}; "
        f"task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}, {TS_TXT} (90 % CI {TS_CI_TXT}), "
        f"{WORDS[TS_KIND]}; task_duration {fmt(pct(DUR_EST))} % (90 % CI {ci_pct(DUR_C90)}), "
        f"{WORDS[k_dur]}. Paired ABBA, 20 pairs on 4 VMs."
    )
    title = f"Planning {abs(pct(EST)):.0f} % faster, tasks {abs(pct(DUR_EST)):.0f} % slower"
    pl = Plate(title, 536, desc, code=code)
    _metric_panel(pl, 20, "planning_time · s", PAIRS, C90, EST, margin_label=True)
    x0 = 278
    g, _ = glyph(TS_KIND, x0 + len(TS_TXT) * 15.5 + 8, 116, 26)
    pl.add(text(x0, 80, "task_success", "mono f-ink2"), text(x0, 116, TS_TXT, "f-ink bb", 28), g)
    px, x1 = x0 + 30, x0 + 244
    for cx, fails, tok, name, count, changed in (
        (px + 50, TS_N - TS_BASE, "base", "base", f"{TS_BASE}/{TS_N}", set()),
        (px + 140, TS_N - TS_CAND, "cand", "candidate", f"{TS_CAND}/{TS_N}", {TS_BASE}),
    ):
        _run_squares(pl, cx - 32, 150, (TS_N, fails, tok, 3, 18), changed)
        pl.add(
            text(cx, 386, name, "f-ink2", FS, "middle"),
            text(cx, 405, count, "mono f-muted", FS, "middle"),
        )

    def xs(v: float) -> float:
        return px + (v + 0.3) / 0.6 * (x1 - px)

    pl.add(
        h_axis(xs, 306, 334, 0.05, [(0, "0")], 352),
        est_mark(xs, 320, TS_DIFF, TS_KIND),
    )
    _metric_panel(pl, 536, "task_duration · s", DUR, DUR_C90, DUR_EST)
    pl.add(
        run_rows(Strip(20, 430), abba_rows(PAIRS)),
        text(308, 442, "run order →", "f-muted"),
    )
    return pl


class Metric(NamedTuple):
    name: str
    direction: str  # "min" or "max": which way is better
    diffs: list[float]  # per-pair log(candidate / base)
    est: float
    ci: tuple[float, float]

    @property
    def kind(self) -> str:
        return kind_of(self.ci, lower_better=self.direction == "min")


def forest_metrics() -> list[Metric]:
    """Return #1188's 12 metrics, sorted by effect. The draws match its G2 stream.

    Two rows regress: pos_error (its effect is +8 % here, not +2 %) and task_duration
    (drawn from DUR in place of shutdown_time).
    """
    lg = math.log
    spec = [
        ("time_to_simulating", "min", lg(0.93), (lg(0.905), lg(0.957))),
        ("trajectory_time", "min", lg(0.975), (lg(0.93), lg(1.02))),
        ("path_length", "min", lg(0.995), (lg(0.98), lg(1.01))),
        ("tracking_error_rms", "min", lg(1.008), (lg(0.981), lg(1.036))),
        ("smoothness", "max", lg(1.003), (lg(0.988), lg(1.019))),
        ("startup_time", "min", lg(1.01), (lg(0.97), lg(1.045))),
        ("shutdown_time", "min", lg(1.0), (lg(0.965), lg(1.04))),
        ("pos_error", "min", lg(1.08), (lg(1.055), lg(1.105))),
        ("yaw_error", "min", lg(0.99), (lg(0.968), lg(1.012))),
        ("plan_path_stretch", "min", lg(1.0), (lg(0.982), lg(1.018))),
        ("tracking_error_max", "min", lg(1.03), (lg(0.97), lg(1.10))),
    ]
    rng = XorShift(47)
    rows = [
        Metric("planning_time", "min", LOG_DIFF, EST, C90),
        Metric("tracking_error_rms", "min", TRACK_LD, TRACK_EST, TRACK_C90),
        Metric("task_duration", "min", DUR_LD, DUR_EST, DUR_C90),
    ]
    for name, d, e, (a0, a1) in spec:
        s = (a1 - a0) / 2 / 1.729 * math.sqrt(20)
        base = [math.exp(0.08 * rng.norm()) for _ in range(20)]
        cand = [b * math.exp(e + s * rng.norm()) for b in base]
        diffs = [math.log(c / b) for b, c in zip(base, cand, strict=True)]
        m, lo_ci, hi_ci = t_ci(diffs, 1.729)
        if name in {"tracking_error_rms", "shutdown_time"}:
            continue  # drawn from TRACK and DUR; the draws keep the other rows' streams
        rows.append(Metric(name, d, diffs, m, (lo_ci, hi_ci)))
    rows.sort(key=lambda r: r.est)
    return rows


def forest_title(rows: list[Metric]) -> str:
    kinds = [r.kind for r in rows]
    n_imp, n_reg, n_un = (kinds.count(k) for k in ("improved", "regressed", "unsure"))
    n_eq = kinds.count("equiv") + kinds.count("small")
    return f"{n_imp} better, {n_reg} worse, {n_un} unclear, {n_eq} same"


def plate_forest(code: str) -> Plate:
    rows = forest_metrics()
    desc = "12 metrics, change vs base against the ±5 % margin band: " + "; ".join(
        f"{r.name} {fmt(pct(r.est))} % (90 % CI {ci_pct(r.ci)}), {WORDS[r.kind]}" for r in rows
    )
    pitch, top = 38, 92
    bottom = top + pitch * (len(rows) - 1)
    pl = Plate(forest_title(rows), bottom + 96, desc, code=code)
    lo, hi = axis_range([d for r in rows for d in r.diffs], 0.04)
    ax0, ax1 = 220, 722

    def xs(v: float) -> float:
        return ax0 + (v - lo) / (hi - lo) * (ax1 - ax0)

    pl.add(h_axis(xs, top - 24, bottom + 24, MARGIN, pct_ticks(lo, hi), bottom + 46))
    for i, r in enumerate(rows):
        y = top + i * pitch
        pl.add(text(20, y + 5, r.name, "mono f-ink2"))
        dx = [xs(d) for d in r.diffs]
        pl.add(
            *(
                circle(x, y + 7 + o * 0.5, 2.2, "f-cand", fill_opacity=0.5)
                for x, o in zip(dx, swarm(dx, 2.2, one_sided=True), strict=True)
            )
        )
        pl.add(est_mark(xs, y - 6, r.est, r.kind, pl))
        g, _ = glyph(r.kind, ax1 + 22, y + 5, FS + 3)
        pl.add(g)
    pl.add(
        text((ax0 + ax1) / 2, bottom + 70, "change vs base", "f-ink2", FS, "middle"),
        legend(W - 20, 66, [("f-cand", "one pair"), ("f-band", "±5 % margin")]),
    )
    return pl


def plate_est(code: str) -> Plate:
    """Draw planning_time as two dot columns."""
    kind = plan_kind()
    desc = (
        f"planning_time, 20 ABBA pairs on 4 VMs: {sum(p.cand < p.base for p in PAIRS)} of 20 "
        f"pairs faster. Effect {fmt(pct(EST))} %, 90 % CI {ci_pct(C90)}, "
        f"{WORDS[kind]}."
    )
    pl = Plate(plan_title(), 480, desc, (kind, f"{fmt(pct(EST))} %"), code)
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    pl.add(
        dot_panel(
            pl,
            x0=20,
            x1=500,
            y0=80,
            y1=420,
            base=[p.base for p in PAIRS],
            cand=[p.cand for p in PAIRS],
            lo=lo,
            hi=hi,
            ci=C90,
            ticks=nice_ticks(lo, hi, 5),
            tick_fmt=lambda t: f"{t:.1f} s",
            labels="one",
            r=5.5,
            margin_label=True,
            connector=True,
        ),
        run_rows(Strip(540, 120, cell=14, pair_gap=5, pitch=24, label_w=54), abba_rows(PAIRS)),
        text(594, 236, "run order →", "f-muted"),
    )
    return pl


SK_CI = newcombe(SK_BASE, SK_N, SK_CAND, SK_N)  # candidate kill rate minus base
SK_DIFF = (SK_CAND - SK_BASE) / SK_N


def plate_waffle(code: str) -> Plate:
    sk_kind = kind_of(SK_CI, lower_better=True, d=0.05)
    desc = (
        f"task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}: {TS_TXT}, 90 % CI {TS_CI_TXT}, "
        f"{WORDS[TS_KIND]}. required_sigkill: base {SK_BASE}/{SK_N} killed, candidate "
        f"{SK_CAND}/{SK_N}, {fmt(SK_DIFF * 100)} pp, 90 % CI "
        f"[{fmt(SK_CI[0] * 100)}, {fmt(SK_CI[1] * 100)}] pp, {WORDS[sk_kind]}."
    )
    pl = Plate("Flake fixed; success still unclear", 340, desc, code=code)
    g, _ = glyph(TS_KIND, 138, 120, 26)
    pl.add(
        text(20, 82, "task_success", "mono f-ink2"),
        text(20, 120, TS_TXT, "f-ink bb", 28),
        g,
        text(20, 165, "base"),
        text(20, 215, "candidate"),
    )
    _run_squares(pl, 110, 146, (TS_N, TS_N - TS_BASE, "base", 9, 18), set())
    flipped = set(range(TS_BASE, TS_CAND))  # failed on base, passed on the candidate
    _run_squares(pl, 110, 196, (TS_N, TS_N - TS_CAND, "cand", 9, 18), flipped)
    pl.add(
        text(330, 165, f"{TS_BASE}/{TS_N}", "mono f-muted"),
        text(330, 215, f"{TS_CAND}/{TS_N}", "mono f-muted"),
    )

    def sc(v: float) -> float:
        return 110 + (v + 0.3) / 0.6 * 220

    pp = [(v, "0" if v == 0 else f"{fmt(v * 100, 0)} pp") for v in (-0.2, 0, 0.2)]
    pl.add(
        text(20, 277, "change"),
        h_axis(sc, 257, 285, 0.05, pp, 310),
        est_mark(sc, 271, TS_DIFF, TS_KIND),
    )
    fx = 420
    g, _ = glyph(sk_kind, fx + 226, 120, 26)
    pl.add(
        text(fx, 82, "required_sigkill", "mono f-ink2"),
        text(fx, 120, f"{SK_BASE / SK_N * 100:.0f} % → ≤ {SK_BOUND * 100:.1f} %", "f-ink bb", 28),
        g,
        text(fx, 165, "base"),
        text(fx, 215, "candidate"),
    )
    _run_squares(pl, fx + 90, 150, (SK_N, SK_BASE, "base", 15, 14), set())
    killed = set(range(SK_N - SK_BASE, SK_N))  # killed on base, clean on the candidate
    _run_squares(pl, fx + 90, 200, (SK_N, SK_CAND, "cand", 15, 14), killed)
    rx0, rx1 = fx + 90, 770

    def rs(v: float) -> float:
        return rx0 + (v + 0.3) / 0.4 * (rx1 - rx0)

    pp = [(v, "0" if v == 0 else f"{fmt(v * 100, 0)} pp") for v in (-0.2, -0.1, 0)]
    pl.add(
        text(fx, 277, "change"),
        h_axis(rs, 257, 285, 0.05, pp, 310),
        est_mark(rs, 271, SK_DIFF, sk_kind),
    )
    return pl


def plate_sweep(code: str) -> Plate:
    sp = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    rng = XorShift(59)
    groups = []
    for v in sp:
        eff = 0.0 if v < 0.6 else -0.06 - 0.08 * (v - 0.6)
        b0 = 0.9 + 1.1 * v
        base = [b0 * math.exp(0.035 * rng.norm()) for _ in range(6)]
        cand = [b * math.exp(eff + 0.03 * rng.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], 2.015)
        groups.append(
            (v, base, cand, m, (lo_ci, hi_ci), kind_of((lo_ci, hi_ci), lower_better=True))
        )
    last = groups[-1]
    desc = "drive_time, 8 speeds x 6 paired repeats: " + "; ".join(
        f"{g[0]} m/s {fmt(pct(g[3]))} % (90 % CI {ci_pct(g[4])}), {WORDS[g[5]]}" for g in groups
    )
    first = next(g[0] for g in groups if g[5] in MOVED)
    pl = Plate(f"Faster from {first:.1f} m/s", 460, desc, (last[5], f"{fmt(pct(last[3]))} %"), code)
    x0, x1, y0, y1, lo, hi = 74, 790, 80, 370, 0.95, 2.95

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    for t in (1.0, 1.5, 2.0, 2.5):
        pl.add(
            line(x0, ys(t), x1, ys(t), "s-grid"),
            text(x0 - 8, ys(t) + 5, f"{t:.1f} s", "mono f-muted", FS, "end"),
        )
    step = (x1 - x0) / len(sp)
    mids = []
    for k, (v, base, cand, _m, ci, kind) in enumerate(groups):
        gx = x0 + (k + 0.5) * step
        g, _ = glyph(kind, gx - 4, ys(max(base + cand)) - 16, FS + 2)
        pl.add(
            dot_panel(
                pl,
                x0=gx - 38,
                x1=gx + 42,
                y0=y0,
                y1=y1,
                base=base,
                cand=cand,
                lo=lo,
                hi=hi,
                ci=ci,
                tick_labels=False,
                labels="none",
                r=3.4,
            ),
            g,
            text(gx - 6, y1 + 26, f"{v:.1f}", "mono f-muted", FS, "middle"),
        )
        mx = gx - 38 + 80 * 0.435  # midway between the base and candidate columns
        mids.append((mx, ys(quant(base, 0.5)), ys(quant(cand, 0.5)), kind))
    for col, tok in ((1, "base"), (2, "cand")):
        d = "M" + "L".join(f"{num(p[0])} {num(p[col])}" for p in mids)
        pl.add(el("path", d=d, cls=f"s-{tok}", fill="none", stroke_width=2, stroke_opacity=0.8))
    for mx, yb, yc, kind in mids:  # the gap at each speed: base median to candidate median
        if kind in MOVED:
            mark = VERDICT[kind][0]
            pl.add(line(mx, yb, mx, yc, f"s-{mark} medflow {pl.flow(FLOW)}", 2))
        else:
            pl.add(line(mx, yb, mx, yc, "s-muted dash", 1.5, stroke_opacity=0.6))
    pl.add(
        text((x0 + x1) / 2, y1 + 54, "speed (m/s)", "f-ink2", FS, "middle"),
        legend(W - 20, y1 + 54, ARMS),
    )
    return pl


def plate_design(code: str) -> Plate:
    p_est, p_ci = DES_PAIRED
    b_est, b_ci = DES_BLOCKED
    p_kind, b_kind = kind_of(p_ci, lower_better=True), kind_of(b_ci, lower_better=True)
    desc = (
        f"A metric with no real change on VMs that slow down {DRIFT * 100:.1f} % per run. "
        f"Paired ABBA on 4 VMs: {fmt(pct(p_est))} %, 90 % CI {ci_pct(p_ci)}, "
        f"{WORDS[p_kind]}. Blocked, all base then all candidate on one VM: "
        f"{fmt(pct(b_est))} %, 90 % CI {ci_pct(b_ci)}, {WORDS[b_kind]}: "
        "the drift lands on the one boundary between the blocks."
    )
    pl = Plate("Blocked runs fake a slowdown", 300, desc, code=code)
    pl.legend = True
    st = Strip(20, 92, cell=14, h=12, gap=3, pair_gap=6, pitch=22, label_w=58)
    rows = abba_rows(DES)
    pl.add(text(20, 76, "paired ABBA", "f-ink2 b"), run_rows(st, rows))
    for r, (_, seq) in enumerate(rows):  # an arc under each pair, still
        yb = st.y(r) + st.h + 1.5
        for j in range(0, len(seq), 2):
            ia = j + seq[j : j + 2].index("A")
            ib = j + seq[j : j + 2].index("B")
            xa, xb = st.x(ia) + st.cell / 2, st.x(ib) + st.cell / 2
            d = f"M{num(xa)} {num(yb)}Q{num((xa + xb) / 2)} {num(yb + 7)} {num(xb)} {num(yb)}"
            pl.add(el("path", d=d, cls="s-cand", fill="none", stroke_width=1.4, stroke_opacity=0.7))
    blk = Strip(20, 214, cell=14, h=12, gap=3, label_w=58, pairs=False)
    edge = blk.x(10) - blk.gap / 2
    mark = VERDICT[b_kind][0]
    pl.add(
        text(20, 198, "blocked", "f-ink2 b"),
        run_rows(blk, [("VM 1", "A" * 10 + "B" * 10)]),
        el(
            "path",
            d=f"M{num(edge)} {num(206)}L{num(edge)} {num(234)}",
            cls=f"s-{mark}",
            fill="none",
            stroke_width=2.5,
        ),
        line(78, 252, 440, 252, "s-muted"),
        el("path", d="M440 247L449 252L440 257Z", cls="f-muted"),
        text(458, 257, "run order", "f-muted"),
    )
    lo, hi = math.log(0.91), math.log(1.15)
    ax0, ax1 = 540, 750

    def xs(v: float) -> float:
        return ax0 + (v - lo) / (hi - lo) * (ax1 - ax0)

    yp, yk = st.y(1) + st.h + 5, blk.y(0) + blk.h / 2
    pl.add(
        h_axis(xs, 70, 240, MARGIN, pct_ticks(lo, hi, 3), 262),
        est_mark(xs, yp, p_est, p_kind),
        est_mark(xs, yk, b_est, b_kind),
        text((ax0 + ax1) / 2, 284, "change", "f-ink2", FS, "middle"),
    )
    for yy, kind in ((yp, p_kind), (yk, b_kind)):
        g, _ = glyph(kind, ax1 + 18, yy + 6, FS + 3)
        pl.add(g)
    return pl


# a synthetic history of 30 commits. The last one is this PR, with the paired effect.
_HR = XorShift(1010)
HIST: list[list[float]] = []
_level = quant([p.base for p in PAIRS], 0.5)
for _k in range(30):
    _level *= math.exp(EST) if _k == 29 else math.exp(0.006 * _HR.norm())
    HIST.append([_level * math.exp(0.05 * _HR.norm()) for _ in range(6)])
HIST_MED = [quant(h, 0.5) for h in HIST]
HIST_STEP = math.log(HIST_MED[-1] / HIST_MED[-2])
# the commit noise: twice the spread of the median's step from one commit to the next
HIST_NOISE = 2 * sd([math.log(HIST_MED[k + 1] / HIST_MED[k]) for k in range(28)])


def plate_history(code: str) -> Plate:
    out_of_band = abs(HIST_STEP) > HIST_NOISE
    kind = ("improved" if HIST_STEP < 0 else "regressed") if out_of_band else "unsure"
    desc = (
        "Synthetic history: planning_time on 30 commits, 6 runs each; the last commit is this "
        f"PR. Its median steps {fmt(pct(HIST_STEP))} % from the commit before, out of the "
        f"±{pct(HIST_NOISE):.0f} % commit-noise band."
    )
    pl = Plate("This PR steps planning down", 420, desc, (kind, f"{fmt(pct(HIST_STEP))} %"), code)
    x0, x1, y0, y1 = 74, 780, 80, 350
    lo, hi = axis_range([v for h in HIST for v in h])
    step = (x1 - x0) / len(HIST)

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    def xc(k: int) -> float:
        return x0 + (k + 0.5) * step

    ref = HIST_MED[-2]
    top, bot = ys(ref * math.exp(HIST_NOISE)), ys(ref * math.exp(-HIST_NOISE))
    pl.add(
        rect(x0, top, x1 - x0, bot - top, "f-band s-bandEdge", stroke_width=1),
        text(x0 + 8, bot - 8, "commit noise", "f-muted"),
    )
    for t in nice_ticks(lo, hi, 4):
        pl.add(
            line(x0, ys(t), x1, ys(t), "s-grid"),
            text(x0 - 8, ys(t) + 5, f"{t:.2f} s", "mono f-muted", FS, "end"),
        )
    d = ""
    for k, m in enumerate(HIST_MED[:-1]):
        d += f"{'L' if d else 'M'}{num(xc(k) - step / 2)} {num(ys(m))}H{num(xc(k) + step / 2)}"
    pl.add(el("path", d=d, cls="s-ink2", fill="none", stroke_width=2, stroke_opacity=0.7))
    xe = xc(len(HIST) - 1) - step / 2
    mark = VERDICT[kind][0]
    y_prev, y_pr = ys(HIST_MED[-2]), ys(HIST_MED[-1])
    pl.add(line(xe, y_pr, x1, y_pr, f"s-{mark}", 2.5))
    # the step from the commit before to the PR's median: the median connector
    if out_of_band:
        pl.add(line(xe, y_prev, xe, y_pr, f"s-{mark} medflow {pl.flow(FLOW)}", 2.5))
    else:
        pl.add(line(xe, y_prev, xe, y_pr, f"s-{mark} dash", 2.5, stroke_opacity=0.5))
    for k, h in enumerate(HIST):
        tok = "cand" if k == len(HIST) - 1 else "base"
        py = [ys(v) for v in h]
        pl.add(
            *(
                circle(xc(k) + o, y, 2.6, f"f-{tok} s-plate", stroke_width=0.8)
                for y, o in zip(py, swarm(py, 2.6), strict=True)
            )
        )
    for k in (0, 9, 19):
        pl.add(text(xc(k), y1 + 26, str(k + 1), "mono f-muted", FS, "middle"))
    pl.add(
        text(xc(len(HIST) - 1), y1 + 26, "PR", "mono f-ink2 b", FS, "middle"),
        text((x0 + x1) / 2, y1 + 54, "commit (synthetic history)", "f-ink2", FS, "middle"),
    )
    return pl


# ---------------------------------------------------------------- appendix: how flow looks


def look_variants() -> list[list[tuple[str, Look]]]:
    """Return the grid rows: speed, pattern, contrast. The others stay at S2 P2 C2."""
    _, s2 = SPEEDS["S2"]
    _, d2, g2 = PATTERNS["P2"]
    c2 = CONTRASTS["C2"]
    speed = [(f"{k} {w}", Look(k, v, d2, g2, c2)) for k, (w, v) in SPEEDS.items()]
    pattern = [(f"{k} {w}", Look(k, s2, d, g, c2)) for k, (w, d, g) in PATTERNS.items()]
    contrast = [(f"{k} {c:g}", Look(k, s2, d2, g2, c)) for k, c in CONTRASTS.items()]
    return [speed, pattern, contrast]


def plate_looks(code: str) -> Plate:
    desc = (
        "The planning_time panel (only the median connector flows) in nine looks. Speed "
        "S1-S3 is 4, 8 and 16 px/s. Pattern P1-P3 is 1-3, 4-4 and 8-6 px. Contrast C1-C3 is "
        "the connector's stroke opacity."
    )
    pl = Plate("Pick a speed, pattern, contrast", 676, desc, code=code)
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    for r, row in enumerate(look_variants()):
        for k, (label, look) in enumerate(row):
            x0, y = 20 + k * 258, 62 + r * 204
            pl.add(
                text(x0 + 4, y + 18, label, "mono f-ink2 b"),
                dot_panel(
                    pl,
                    x0=x0,
                    x1=x0 + 244,
                    y0=y + 32,
                    y1=y + 190,
                    base=[p.base for p in PAIRS],
                    cand=[p.cand for p in PAIRS],
                    lo=lo,
                    hi=hi,
                    ci=C90,
                    tick_labels=False,
                    labels="none",
                    r=2.8,
                    connector=True,
                    look=look,
                ),
            )
    return pl


PLATES = {
    "d1_verdicts.svg": lambda: plate_verdicts("D1 · ▲ ▼ ≈ ?"),
    "d2_scorecard.svg": lambda: plate_scorecard("D2 · scorecard · one ▼"),
    "d3_forest.svg": lambda: plate_forest("D3 · forest · 0 → estimate flows on ▲▼ rows"),
    "d4_estimation.svg": lambda: plate_est("D4 · estimation"),
    "d5_waffle.svg": lambda: plate_waffle("D5 · waffle"),
    "d6_sweep.svg": lambda: plate_sweep("D6 · sweep · ≈ points are still"),
    "d7_design.svg": lambda: plate_design("D7 · design"),
    "d8_history.svg": lambda: plate_history("D8 · history · synthetic"),
    "a1_looks.svg": lambda: plate_looks("A1 · S speed · P pattern · C contrast"),
}

# ---------------------------------------------------------------- the motion rule, checked

SMIL = {"animate", "animateTransform", "animateMotion", "set", "animateColor"}
STROKED = {"line", "path", "rect", "polyline"}


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def check_motion(path: Path) -> tuple[int, list[str]]:
    """Check the motion rule on one SVG and return (animated elements, errors).

    The rule: only stroke-dashoffset animates; only dashed strokes animate; every animated
    element carries the class that prefers-reduced-motion stops; there is no SMIL and no
    transition.
    """
    errs: list[str] = []
    root = ET.parse(path).getroot()  # noqa: S314 - our own generated files
    css = "".join(s.text or "" for s in root.iter() if _strip_ns(s.tag) == "style")
    if "transition" in css:
        errs.append("css has a transition")
    keyframes = {}
    for m in re.finditer(r"@keyframes\s+([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", css):
        keyframes[m.group(1)] = m.group(2)
        props = {
            d.split(":", 1)[0].strip()
            for blk in re.findall(r"\{([^{}]*)\}", m.group(2))
            for d in blk.split(";")
            if d.strip()
        }
        if props != {"stroke-dashoffset"}:
            errs.append(f"@keyframes {m.group(1)} animates {sorted(props)}")
    rest = re.sub(r"@keyframes\s+[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", css)
    reduced = re.search(r"prefers-reduced-motion:reduce\)\{([^{}]*\{[^{}]*\})\}", rest)
    if not reduced or reduced.group(1) != ".fl{animation:none!important}":
        errs.append("no prefers-reduced-motion rule that stops .fl")
        rest_rules = rest
    else:
        rest_rules = rest.replace(reduced.group(0), "")
    animated: set[str] = set()
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", rest_rules):
        sel, body = m.group(1).strip(), m.group(2)
        decls = {
            k.strip(): v.strip() for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d)
        }
        if not any(k.startswith("animation") for k in decls):
            continue
        if not re.fullmatch(r"\.[\w-]+", sel):
            errs.append(f"animation on a selector that is not one class: {sel}")
            continue
        if "stroke-dasharray" not in decls:
            errs.append(f"{sel} animates without stroke-dasharray")
        name = decls.get("animation", "").split()[0]
        if name not in keyframes:
            errs.append(f"{sel} uses unknown keyframes {name}")
        animated.add(sel[1:])
    count = 0
    for e in root.iter():
        tag = _strip_ns(e.tag)
        if tag in SMIL:
            errs.append(f"SMIL element <{tag}>")
        if "style" in e.attrib and "anim" in e.attrib["style"]:
            errs.append(f"inline animation style on <{tag}>")
        classes = set(e.attrib.get("class", "").split())
        if not classes & animated:
            continue
        count += 1
        if "fl" not in classes:
            errs.append(f"<{tag}> animates without the .fl class")
        if tag not in STROKED:
            errs.append(f"<{tag}> animates but is not a stroked line")
        if tag != "line" and e.attrib.get("fill") != "none":
            errs.append(f"<{tag} class={e.attrib['class']!r}> animates and has a fill")
    return count, errs


# The kinds of element that may flow, by class: the median connector, the forest
# connector from 0 to the estimate, and the outline of failed or changed runs. Anything
# else that flows fails the check.
SALIENT = ("medflow", "estflow", "runflag")
# Classes of the marks this demo dropped: likely-range bands, CI bars, capped intervals,
# whiskers, decision leaders and flowing pair lines. A plate that still has one fails.
GONE = {
    "range",
    "likely",
    "ci",
    "cap",
    "caps",
    "whisker",
    "whiskers",
    "lead",
    "pairflow",
}
GONE_WORDS = ("likely range", "likely-range", "whisker")


def check_salience(path: Path) -> tuple[dict[str, int], list[str]]:
    """Check that only the salient lines flow, and that no interval mark is left.

    Each .fl element must be a median connector (.medflow), a forest connector
    (.estflow) or the outline of the runs that failed or changed outcome (.runflag). No
    element may carry a GONE class or a data-verdict band, and no text may name a likely
    range or a whisker.
    """
    root = ET.parse(path).getroot()  # noqa: S314 - our own generated files
    errs: list[str] = []
    counts = dict.fromkeys(SALIENT, 0)
    for e in root.iter():
        tag = _strip_ns(e.tag)
        classes = set(e.attrib.get("class", "").split())
        left = classes & GONE
        if left:
            errs.append(f"<{tag}> has a dropped mark class {sorted(left)}")
        if "data-verdict" in e.attrib:
            errs.append(f"<{tag}> is a verdict band")
        if tag in {"text", "title"} and any(w in (e.text or "").lower() for w in GONE_WORDS):
            errs.append(f"<{tag}> names a dropped mark: {e.text!r}")
        if "fl" not in classes:
            continue
        kinds = [k for k in SALIENT if k in classes]
        if len(kinds) != 1:
            errs.append(f"<{tag} class={e.attrib['class']!r}> flows, not salient")
            continue
        counts[kinds[0]] += 1
    return counts, errs


def main() -> None:
    if "--check" in sys.argv:
        bad, total = 0, 0
        for path in sorted(OUT.glob("*.svg")):
            count, errs = check_motion(path)
            counts, s_errs = check_salience(path)
            errs += s_errs
            total += count
            if sum(counts.values()) != count:
                errs.append(f"{count} animated, {sum(counts.values())} salient")
            size = path.stat().st_size
            if size >= 150_000:
                errs.append(f"{size} bytes, over 150 KB")
            bad += bool(errs)
            status = "ok" if not errs else "FAIL " + "; ".join(errs)
            kinds = " ".join(f"{k}={v}" for k, v in counts.items() if v)
            sys.stdout.write(
                f"{path.name}: {count} flowing ({kinds or 'none'}), {size} B, {status}\n"
            )
        sys.stdout.write(f"total {total} flowing elements; {bad} files fail\n")
        sys.exit(1 if bad else 0)
    if "--captions" in sys.argv:
        for name, make in PLATES.items():
            sys.stdout.write(f"{name}: {make().desc}\n")
        return
    if "--facts" in sys.argv:
        rows = forest_metrics()
        sys.stdout.write(
            f"planning {fmt(pct(EST))} % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}]\n"
            f"startup {fmt(pct(UNS_EST))} % CI [{fmt(pct(UNS_C90[0]))}, {fmt(pct(UNS_C90[1]))}]\n"
            f"design paired {DES_PAIRED} blocked {DES_BLOCKED}\n"
            f"task_success {TS_CI} sigkill {SK_CI}\n"
            f"forest {forest_title(rows)}: "
            + ", ".join(f"{r.name} {r.kind}" for r in rows)
            + f"\nhistory step {fmt(pct(HIST_STEP))} % noise {pct(HIST_NOISE):.1f} %\n"
        )
        return
    for old in OUT.glob("*.svg"):
        if old.name not in PLATES:
            old.unlink()
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
