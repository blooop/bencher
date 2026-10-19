"""Write the progressive-drawing evidence demo plates as standalone SVG files.

The data are synthetic and seeded, and they are the data of the #1188 demo, so every run
writes the same files. The script uses only the standard library:

    python docs/evidence_progressive_demo/make_svgs.py

Each plate draws itself the way the experiment made it: one run at a time, in run order.
A run's dot drops into its exact place in its column and a ring marks the landing. Once
both runs of a pair are in, the pair line draws from the base dot to the candidate dot.
When every run is in, the medians grow, the ±Δ band fades in, the CI draws from its bottom
cap to its top cap, and the finding (title, number, verdict glyph) comes last.

The draw takes at most 8 s of a 20 s loop, so the complete chart holds for more than 10 s
before it fades and draws again. The animation is CSS keyframes only. Each mark's plain
style is its final state, so ``prefers-reduced-motion`` shows the complete chart. Each SVG
carries a light and a dark palette (``prefers-color-scheme``).
"""

# ruff: noqa: PLR2004, RUF001
# PLR2004: a plot is mostly literal coordinates. RUF001: the labels use the real minus
# sign, the approximately-equal sign and arrows on purpose.

from __future__ import annotations

import itertools
import math
import sys
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


def barnard(k1: int, n1: int, k2: int, n2: int, grid: int = 2000) -> float:
    """Return the two-sided p of Barnard's exact test (pooled z statistic)."""

    def stat(a: int, b: int) -> float:
        pp = (a + b) / (n1 + n2)
        v = pp * (1 - pp) * (1 / n1 + 1 / n2)
        return 0.0 if v == 0 else (b / n2 - a / n1) / math.sqrt(v)

    t_obs = abs(stat(k1, k2))
    extreme = [
        (a, b) for a in range(n1 + 1) for b in range(n2 + 1) if abs(stat(a, b)) >= t_obs - 1e-12
    ]
    best = 0.0
    for g in range(1, grid):
        pi = g / grid
        tot = sum(
            math.comb(n1, a)
            * pi**a
            * (1 - pi) ** (n1 - a)
            * math.comb(n2, b)
            * pi**b
            * (1 - pi) ** (n2 - b)
            for a, b in extreme
        )
        best = max(best, tot)
    return min(best, 1.0)


def mde_prop(k: int, n: int) -> float:
    """Return the smallest change in a rate that n runs per arm detect (80 % power)."""
    p = k / n
    return (Z90 + Z80) * math.sqrt(2 * p * (1 - p) / n)


def wilcoxon_p(diffs: list[float]) -> float:
    """Return the exact two-sided p of the Wilcoxon signed-rank test (no ties)."""
    n = len(diffs)
    ranks = {i: r + 1 for r, i in enumerate(sorted(range(n), key=lambda i: abs(diffs[i])))}
    w = sum(ranks[i] for i in range(n) if diffs[i] > 0)
    dist = [1] + [0] * (n * (n + 1) // 2)
    for r in range(1, n + 1):
        for t in range(len(dist) - 1, r - 1, -1):
            dist[t] += dist[t - r]
    tot = 2**n
    lo, hi = sum(dist[: w + 1]) / tot, sum(dist[w:]) / tot
    return min(1.0, 2 * min(lo, hi))


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
TS_P = barnard(TS_BASE, TS_N, TS_CAND, TS_N)
TS_MDE = mde_prop(TS_BASE, TS_N)
SK_BASE, SK_CAND, SK_N = 4, 0, 30
SK_BOUND = zero_fail_bound(SK_N)
SK_RUNS = {b: runs_for_bound(b) for b in (0.05, 0.01)}
WILCOXON_P = wilcoxon_p(LOG_DIFF)

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


def swarm(pos: list[float], r: float, one_sided: bool = False) -> list[float]:
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


ARMS = [("f-base", "base"), ("f-cand", "candidate")]


# ---------------------------------------------------------------- the clock

CYCLE = 20.0  # s: one loop. The draw ends by 8 s, the chart holds, then fades and loops.
TAIL = 0.6  # s: the fade out at the end of a loop
DROP = 0.22  # s: one dot falls into its place
DROP_DY = 18  # px: the distance it falls
LINK = 0.25  # s: a pair line draws itself
T0 = 0.4  # s: the first run lands

BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
.ring{{opacity:0;fill:none;transform-box:fill-box;transform-origin:center}}
.grow,.pop{{transform-box:fill-box;transform-origin:center}}
.dr{{stroke-dasharray:1 1}}
@media (prefers-reduced-motion:reduce){{.a{{animation:none!important}}}}
"""


def pc(t: float) -> str:
    s = f"{min(max(t, 0.0), CYCLE) / CYCLE * 100:.3f}".rstrip("0").rstrip(".")
    return f"{s}%"


class Clock:
    """Give each mark a CSS animation that starts at its own time in one shared loop.

    Every mark runs the same CYCLE from 0 s, so all marks stay in step loop after loop.
    The times sit in the keyframes, one keyframe set per distinct start time. A mark's
    plain style is its final state, so with ``prefers-reduced-motion`` (animations off)
    the complete chart shows.
    """

    def __init__(self) -> None:
        self.css: list[str] = []
        self._made: dict[tuple[str, float, float], str] = {}
        self.end = 0.0

    def _make(self, key: tuple[str, float, float], stops: list[tuple[float, str]]) -> str:
        if key not in self._made:
            name = f"k{len(self._made)}"
            self._made[key] = name
            body = "".join(f"{pc(t)}{{{css}}}" for t, css in stops)
            self.css.append(
                f"@keyframes {name}{{{body}}}.{name}{{animation:{name} {CYCLE:g}s linear infinite}}"
            )
        return f"a {self._made[key]}"

    def _show(
        self, kind: str, t: float, dur: float, start: str, end: str, o0: float = 1, ease: str = ""
    ) -> str:
        """Hide a mark until t, change it from start to end over dur, hold, fade at the tail."""
        self.end = max(self.end, t + dur)
        e = f";animation-timing-function:{ease}" if ease else ""
        sep = ";" if start else ""
        stops = [
            (0, f"opacity:0{sep}{start}"),
            (t - 0.01, f"opacity:0{sep}{start}"),
            (t, f"opacity:{o0:g}{sep}{start}{e}"),
            (t + dur, f"opacity:1{';' if end else ''}{end}"),
            (CYCLE - TAIL, f"opacity:1{';' if end else ''}{end}"),
            (CYCLE, f"opacity:0{';' if end else ''}{end}"),
        ]
        return self._make((kind, round(t, 3), dur), stops)

    def drop(self, t: float) -> str:
        """A dot falls DROP_DY px into its exact place."""
        return self._show(
            "drop",
            t,
            DROP,
            f"transform:translateY(-{DROP_DY}px)",
            "transform:none",
            ease="cubic-bezier(.55,0,.95,.6)",
        )

    def ring(self, t: float, scale: float = 2.6, dur: float = 0.4) -> str:
        """A ring spreads from the place where a run just landed, then goes."""
        stops = [
            (0, "opacity:0;transform:scale(1)"),
            (t - 0.01, "opacity:0;transform:scale(1)"),
            (t, "opacity:.9;transform:scale(1)"),
            (t + dur, f"opacity:0;transform:scale({scale:g})"),
            (CYCLE, f"opacity:0;transform:scale({scale:g})"),
        ]
        return self._make(("ring", round(t, 3), dur), stops)

    def draw(self, t: float, dur: float) -> str:
        """A stroke draws itself from its first point (the mark needs pathLength=1)."""
        return self._show("draw", t, dur, "stroke-dashoffset:1", "stroke-dashoffset:0")

    def fade(self, t: float, dur: float = 0.35) -> str:
        return self._show("fade", t, dur, "", "", o0=0)

    def grow(self, t: float, dur: float = 0.3) -> str:
        """A bar grows out from its centre (class grow)."""
        return f"grow {self._show('grow', t, dur, 'transform:scaleX(0)', 'transform:none')}"

    def pop(self, t: float, dur: float = 0.2) -> str:
        """A square grows from a point at its centre (class pop)."""
        return f"pop {self._show('pop', t, dur, 'transform:scale(.2)', 'transform:none')}"


def run_times(orders: list[str], step: float, t0: float = T0) -> tuple[list[float], list[float]]:
    """Return when each pair's base ("A") and candidate ("B") run landed, in run order."""
    tb: list[float] = []
    tc: list[float] = []
    k = 0
    for order in orders:
        for arm in order:
            (tb if arm == "A" else tc).append(t0 + k * step)
            k += 1
    return tb, tc


def abba(n: int) -> list[str]:
    """Return the order of n pairs: AB, BA, AB, ... each pair back to back on one VM."""
    return ["BA" if j % 2 else "AB" for j in range(n)]


class Plate:
    def __init__(
        self, title: str, height: float, desc: str, big: tuple[str, str] | None = None
    ) -> None:
        self.title, self.height, self.desc, self.big = title, height, desc, big
        self.parts: list[str] = []
        self.clk = Clock()
        self.reveal = 0.0  # when the finding (title and big number) appears

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    @staticmethod
    def _palette(pal: dict[str, str]) -> str:
        return "".join(f".f-{k}{{fill:{v}}}.s-{k}{{stroke:{v}}}" for k, v in pal.items())

    def render(self) -> str:
        h = num(float(self.height))
        last = self.clk.fade(self.reveal, 0.4)
        head = [
            rect(0.5, 0.5, W - 1, self.height - 1, "f-plate s-rule", rx=6),
            text(20, 40, self.title, f"f-ink bb {last}", 23),
        ]
        if self.big:
            kind, s = self.big
            gw = 30 * 0.74
            g, _ = glyph(kind, W - 20 - gw, 42, 30, last)
            head += [g, text(W - 30 - gw, 42, s, f"f-ink bb {last}", 30, "end")]
        end = self.clk.end
        if end > 8.0 or CYCLE - TAIL - end < 10:
            msg = f"{self.title}: the draw ends at {end:.2f} s; keep it under 8 s"
            raise ValueError(msg)
        css = (
            BASE_CSS
            + self._palette(LIGHT)
            + "\n@media (prefers-color-scheme:dark){"
            + self._palette(DARK)
            + "}\n"
            + "\n".join(self.clk.css)
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{''.join(head)}{''.join(self.parts)}</svg>\n"
        )


# ---------------------------------------------------------------- shared marks


def columns(
    pl: Plate,
    *,
    box: tuple[float, float, float, float],
    base: list[float],
    cand: list[float],
    tb: list[float],
    tc: list[float],
    lo: float,
    hi: float,
    ci: tuple[float, float],
    est: float,
    kind: str,
    t_stats: float,
    paired: bool = True,
    lower_better: bool = True,
    ticks: list[float] | None = None,
    tick_fmt: Callable[[float], str] | None = None,
    labels: str = "one",
    r: float = 4.5,
    mark_glyph: bool = False,
    rings: bool = True,
    pace: float = 1.0,
    ring_dur: float = 0.4,
) -> float:
    """Draw base and candidate as beeswarm dot columns, one run at a time.

    Each dot lands at its run's time (tb, tc), a ring marks the landing, and a pair line
    draws itself once both runs of a pair are in. From t_stats the medians grow, the ±Δ
    band fades in, and the CI of the shift draws from its bottom cap to its top cap. The
    CI sits beside the candidate column where it puts the candidate median (base median x
    shift). Return the time when the panel is complete.
    """
    clk = pl.clk
    x0, x1, y0, y1 = box

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    back: list[str] = []
    mid: list[str] = []
    front: list[str] = []
    px = x0 + (48 if tick_fmt else 0)
    wid = x1 - px
    cb, cc = px + wid * 0.27, px + wid * 0.6
    for t in ticks or []:
        back.append(line(px, ys(t), x1, ys(t), "s-grid"))
        if tick_fmt:
            back.append(text(px - 7, ys(t) + 5, tick_fmt(t), "mono f-muted", FS, "end"))
    t_med = t_stats
    t_band = t_med + 0.35 * pace
    t_ci = t_band + 0.35 * pace
    t_est = t_ci + 0.45 * pace
    bmed, cmed = quant(base, 0.5), quant(cand, 0.5)
    top, bot = ys(bmed * math.exp(MARGIN)), ys(bmed * math.exp(-MARGIN))
    back.append(
        rect(
            px + 2,
            top,
            x1 - px - 4,
            bot - top,
            f"f-band s-bandEdge {clk.fade(t_band, 0.35 * pace)}",
            stroke_width=1,
        )
    )
    pb, pcd = [ys(v) for v in base], [ys(v) for v in cand]
    ob, oc = swarm(pb, r), swarm(pcd, r)
    mark, _, _ = VERDICT[kind]
    if paired:
        for i in range(len(base)):
            better = (cand[i] < base[i]) == lower_better
            mid.append(
                line(
                    cb + ob[i],
                    pb[i],
                    cc + oc[i],
                    pcd[i],
                    f"s-{'better' if better else 'worse'} dr {clk.draw(max(tb[i], tc[i]) + DROP, LINK)}",
                    1.4,
                    stroke_opacity=0.55,
                    pathLength=1,
                )
            )
    for cx, offs, pos, times, tok in ((cb, ob, pb, tb, "base"), (cc, oc, pcd, tc, "cand")):
        for o, p, t in zip(offs, pos, times, strict=True):
            mid.append(circle(cx + o, p, r, f"f-{tok} s-plate {clk.drop(t)}", stroke_width=1))
            if rings:
                front.append(
                    circle(
                        cx + o,
                        p,
                        r + 1,
                        f"s-ink ring {clk.ring(t + DROP, dur=ring_dur)}",
                        stroke_width=1.5,
                    )
                )
    hws = [min(max(abs(o) for o in offs) + r + 5, wid * 0.15) for offs in (ob, oc)]
    for (cx, med, tok), hw in zip(((cb, bmed, "base"), (cc, cmed, "cand")), hws, strict=True):
        g = clk.grow(t_med, 0.3 * pace)
        mid.append(
            line(cx - hw, ys(med), cx + hw, ys(med), f"s-plate {g}", 9, stroke_linecap="round")
            + line(cx - hw, ys(med), cx + hw, ys(med), f"s-{tok} {g}", 5, stroke_linecap="round")
        )
    bx = min(cc + max(abs(o) for o in oc) + r + 14, x1 - 8)
    y_top, y_bot = sorted((ys(bmed * math.exp(ci[0])), ys(bmed * math.exp(ci[1]))))
    mid.append(
        el(
            "path",
            d=f"M{num(bx - 7)} {num(y_bot)}H{num(bx)}V{num(y_top)}H{num(bx - 7)}",
            cls=f"s-{mark} dr {clk.draw(t_ci, 0.45 * pace)}",
            fill="none",
            stroke_width=3,
            stroke_linecap="round",
            stroke_linejoin="round",
            pathLength=1,
        )
    )
    ye = ys(bmed * math.exp(est))
    mid.append(
        line(bx - 9, ye, bx + 3, ye, f"s-{mark} {clk.fade(t_est, 0.2)}", 3, stroke_linecap="round")
    )
    done = t_est + 0.25 * pace
    if mark_glyph:
        g_, _ = glyph(kind, bx - 9, y_top - 9, FS + 1, clk.fade(done, 0.25))
        mid.append(g_)
    if labels == "one":
        for cx, name, n in ((cb, "base", len(base)), (cc, "candidate", len(cand))):
            back.append(text(cx, y1 + 28, f"{name} n={n}", "f-ink2", FS, "middle"))
    pl.add(*back, *mid, *front)
    return done


def axis_range(vals: list[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return lo - span * pad, hi + span * pad


def oriented(ci: tuple[float, float], lower_better: bool = True) -> tuple[float, float]:
    """Return a CI of a log shift turned so that positive is better."""
    return (-ci[1], -ci[0]) if lower_better else ci


# ---------------------------------------------------------------- plates

STEP = 0.13  # s per run for the 40-run plates


def plate_g3() -> Plate:
    kind = verdict(*oriented(C90), MARGIN)
    desc = (
        f"planning_time, 20 ABBA pairs on 4 VMs, drawn one run at a time in run order: "
        f"{sum(p.cand < p.base for p in PAIRS)} of 20 pairs faster. Effect {fmt(pct(EST))} %, "
        f"90 % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}] %."
    )
    pl = Plate(f"Planning is {abs(pct(EST)):.0f} % faster", 470, desc, (kind, f"{fmt(pct(EST))} %"))
    tb, tc = run_times([p.order for p in PAIRS], STEP)
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    pl.add(text(20, 72, "planning_time · s", "mono f-ink2"))
    pl.reveal = columns(
        pl,
        box=(110, 690, 92, 410),
        base=[p.base for p in PAIRS],
        cand=[p.cand for p in PAIRS],
        tb=tb,
        tc=tc,
        lo=lo,
        hi=hi,
        ci=C90,
        est=EST,
        kind=kind,
        t_stats=max(tb + tc) + DROP + LINK,
        ticks=nice_ticks(lo, hi, 5),
        tick_fmt=lambda t: f"{t:.1f}",
        r=5.5,
    )
    return pl


WORD = {"improved": "faster", "regressed": "slower", "equiv": "unchanged", "small": "unchanged"}


def plate_g1() -> Plate:
    k_plan = verdict(*oriented(C90), MARGIN)
    k_track = verdict(*oriented(TRACK_C90), MARGIN)
    desc = (
        f"planning_time {fmt(pct(EST))} % (90 % CI {fmt(pct(C90[0]))} to {fmt(pct(C90[1]))}), "
        f"{k_plan}; tracking_error_rms {fmt(pct(TRACK_EST))} % (90 % CI "
        f"{fmt(pct(TRACK_C90[0]))} to {fmt(pct(TRACK_C90[1]))}), {k_track}. Paired ABBA, "
        "20 pairs on 4 VMs. Each run lands in both panels at once."
    )
    title = f"Planning {WORD.get(k_plan, 'unclear')}, tracking {WORD.get(k_track, 'unclear')}"
    pl = Plate(title, 470, desc)
    tb, tc = run_times([p.order for p in PAIRS], STEP)
    t_stats = max(tb + tc) + DROP + LINK
    done = 0.0
    panels = [
        ("planning_time · s", PAIRS, C90, EST, k_plan, lambda t: f"{t:.1f}"),
        ("tracking_error · mm", TRACK, TRACK_C90, TRACK_EST, k_track, lambda t: f"{t:g}"),
    ]
    for i, (name, pairs, ci, est, kind, tf) in enumerate(panels):
        x0 = 20 + i * 390
        big = f"{fmt(pct(est))} %"
        lo, hi = axis_range([p.base for p in pairs] + [p.cand for p in pairs])
        done = columns(
            pl,
            box=(x0, x0 + 370, 140, 410),
            base=[p.base for p in pairs],
            cand=[p.cand for p in pairs],
            tb=tb,
            tc=tc,
            lo=lo,
            hi=hi,
            ci=ci,
            est=est,
            kind=kind,
            t_stats=t_stats,
            ticks=nice_ticks(lo, hi),
            tick_fmt=tf,
            r=4.5,
        )
        g, _ = glyph(kind, x0 + len(big) * 15.5 + 8, 116, 26, pl.clk.fade(done, 0.4))
        pl.add(
            text(x0, 80, name, "mono f-ink2"),
            text(x0, 116, big, f"f-ink bb {pl.clk.fade(done, 0.4)}", 28),
            g,
        )
    pl.reveal = done
    return pl


# n = 6 pairs of a metric with a small true change (-3 %): the inconclusive case of #1189,
# with the same generator and seed; here the pairs alternate AB, BA.
SMALL_EFFECT, SMALL_SD = math.log(0.97), 0.07
_SR = XorShift(100)
SMALL: list[Pair] = []
for _p, _o in enumerate(abba(6)):
    _b = 0.42 * SHARD_SPEED[_p % 4] * math.exp(0.18 * _SR.norm())
    SMALL.append(Pair(_p % 4, _p, _b, _b * math.exp(SMALL_EFFECT + SMALL_SD * _SR.norm()), _o))
SMALL_LD = [math.log(p.cand / p.base) for p in SMALL]
SMALL_EST, *_small_ci = t_ci(SMALL_LD, 2.015)  # t(0.95, 5)
SMALL_CI = (_small_ci[0], _small_ci[1])


def plate_small() -> Plate:
    kind = verdict(*oriented(SMALL_CI), MARGIN)
    if kind != "unsure":
        msg = f"the n = 6 plate should be inconclusive, not {kind}"
        raise ValueError(msg)
    desc = (
        f"planning_time, 6 ABBA pairs: {fmt(pct(SMALL_EST))} %, 90 % t interval "
        f"[{fmt(pct(SMALL_CI[0]))}, {fmt(pct(SMALL_CI[1]))}] %, which crosses the ±5 % band: "
        "inconclusive."
    )
    pl = Plate("Six pairs cannot tell", 440, desc, (kind, f"{fmt(pct(SMALL_EST))} %"))
    tb, tc = run_times([p.order for p in SMALL], 0.25)
    vals = [p.base for p in SMALL] + [p.cand for p in SMALL]
    lo, hi = axis_range(vals, 0.15)
    pl.add(text(20, 72, "planning_time · s", "mono f-ink2"))
    pl.reveal = columns(
        pl,
        box=(150, 650, 92, 380),
        base=[p.base for p in SMALL],
        cand=[p.cand for p in SMALL],
        tb=tb,
        tc=tc,
        lo=lo,
        hi=hi,
        ci=SMALL_CI,
        est=SMALL_EST,
        kind=kind,
        t_stats=max(tb + tc) + DROP + LINK,
        ticks=nice_ticks(lo, hi, 5),
        tick_fmt=lambda t: f"{t:.2f}",
        r=7,
    )
    return pl


def forest_rows() -> list[tuple[str, str, list[float], list[float], float, tuple[float, float]]]:
    """Return the 12 metrics of #1188's G2, with the same generator and seed."""
    lg = math.log
    spec = [
        ("time_to_simulating", "min", lg(0.93), (lg(0.905), lg(0.957))),
        ("trajectory_time", "min", lg(0.975), (lg(0.93), lg(1.02))),
        ("path_length", "min", lg(0.995), (lg(0.98), lg(1.01))),
        ("tracking_error_rms", "min", lg(1.008), (lg(0.981), lg(1.036))),
        ("smoothness", "max", lg(1.003), (lg(0.988), lg(1.019))),
        ("startup_time", "min", lg(1.01), (lg(0.97), lg(1.045))),
        ("shutdown_time", "min", lg(1.0), (lg(0.965), lg(1.04))),
        ("pos_error", "min", lg(1.02), (lg(0.99), lg(1.048))),
        ("yaw_error", "min", lg(0.99), (lg(0.968), lg(1.012))),
        ("plan_path_stretch", "min", lg(1.0), (lg(0.982), lg(1.018))),
        ("tracking_error_max", "min", lg(1.03), (lg(0.97), lg(1.10))),
    ]
    rng = XorShift(47)
    bm = quant([p.base for p in PAIRS], 0.5)
    tm = quant([q.base for q in TRACK], 0.5)
    rows = [
        (
            "planning_time",
            "min",
            [p.base / bm for p in PAIRS],
            [p.cand / bm for p in PAIRS],
            EST,
            C90,
        ),
        (
            "tracking_error_rms",
            "min",
            [p.base / tm for p in TRACK],
            [p.cand / tm for p in TRACK],
            TRACK_EST,
            TRACK_C90,
        ),
    ]
    for name, d, e, (a0, a1) in spec:
        s = (a1 - a0) / 2 / 1.729 * math.sqrt(20)
        base = [math.exp(0.08 * rng.norm()) for _ in range(20)]
        cand = [b * math.exp(e + s * rng.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], 1.729)
        med = quant(base, 0.5)
        if name == "tracking_error_rms":
            continue  # drawn above from TRACK; the draws keep the other rows' streams
        rows.append((name, d, [b / med for b in base], [c / med for c in cand], m, (lo_ci, hi_ci)))
    rows.sort(key=lambda r: r[4])
    return rows


def plate_g2() -> Plate:
    rows = forest_rows()
    kinds = [verdict(*oriented(r[5], r[1] == "min"), MARGIN) for r in rows]
    n_imp = kinds.count("improved")
    n_un = kinds.count("unsure") + kinds.count("regressed")
    n_eq = kinds.count("equiv") + kinds.count("small")
    desc = "12 metrics from the same 40 runs, every sample as % of its base median: " + "; ".join(
        f"{r[0]} {fmt(pct(r[4]))} %" for r in rows
    )
    pl = Plate(f"{n_imp} better, {n_un} unclear, {n_eq} same", 616, desc)
    tb, tc = run_times([p.order for p in PAIRS], 0.12)
    t_stats = max(tb + tc) + DROP + LINK
    lo, hi = 0.68, 1.34
    ticks = [0.8, 1.0, 1.2]

    def tf(t: float) -> str:
        return "0" if t == 1.0 else f"{fmt((t - 1) * 100, 0)} %"

    left, pw, ph, pitch = 70, 178, 150, 176
    done = 0.0
    for i, ((name, d, base, cand, m, ci), kind) in enumerate(zip(rows, kinds, strict=True)):
        r, k = divmod(i, 4)
        x0, y = left + k * pw, 66 + r * pitch
        pl.add(text(x0 + 4, y + 18, name, "mono f-ink2"))
        if k == 0:
            for t in ticks:
                yt = y + ph - (t - lo) / (hi - lo) * (ph - 32)
                pl.add(text(left - 6, yt + 5, tf(t), "mono f-muted", FS, "end"))
        done = columns(
            pl,
            box=(x0, x0 + pw - 8, y + 32, y + ph),
            base=base,
            cand=cand,
            tb=tb,
            tc=tc,
            lo=lo,
            hi=hi,
            ci=ci,
            est=m,
            kind=kind,
            t_stats=t_stats + i * 0.05,
            lower_better=d == "min",
            ticks=ticks,
            labels="none",
            r=2.6,
            mark_glyph=True,
            rings=False,
            pace=0.7,
        )
    pl.add(legend(W - 20, 600, [*ARMS, ("f-band", "±5 % of base median")]))
    pl.reveal = done
    return pl


def _pick(rng: XorShift, n: int, k: int) -> set[int]:
    """Return k distinct indices below n, drawn from rng."""
    out: set[int] = set()
    while len(out) < k:
        out.add(math.floor(rng.rnd() * n))
    return out


_FR = XorShift(73)
TS_FAIL = _pick(_FR, TS_N, TS_N - TS_BASE)  # the pairs whose base run failed the task
SK_FAIL = _pick(_FR, SK_N, SK_BASE)  # the pairs whose base run needed SIGKILL


def plate_g5() -> Plate:
    desc = (
        f"task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}: {TS_TXT}, 90 % CI {TS_CI_TXT}, "
        f"inconclusive. required_sigkill: base {SK_BASE}/{SK_N} killed, candidate "
        f"{SK_CAND}/{SK_N}, true rate at most {SK_BOUND * 100:.1f} %: improved. One square per "
        "run, filled in run order; a pair's two runs sit one above the other."
    )
    pl = Plate("Flake fixed; success still unclear", 340, desc)
    clk = pl.clk

    def waffle(
        x0: float, y0: float, times: list[float], fails: set[int], tok: str, cols: int, c: float
    ) -> None:
        g = c * 0.25
        for i, t in enumerate(times):
            r, k = divmod(i, cols)
            x, y = x0 + k * (c + g), y0 + r * (c + g)
            if i in fails:
                h = num(c / 2)
                cross = f"M{num(x + c * 0.25)} {num(y + c * 0.25)}l{h} {h}m0 -{h}l-{h} {h}"
                pl.add(
                    el(
                        "g",
                        rect(x, y, c, c, "f-plate s-worse", rx=3, stroke_width=2)
                        + el("path", d=cross, cls="s-worse", stroke_width=2),
                        cls=clk.pop(t),
                    )
                )
            else:
                pl.add(rect(x, y, c, c, f"f-{tok} {clk.pop(t)}", rx=3))

    def outline(
        x0: float, y0: float, pairs: set[int], times: list[float], cols: int, c: float
    ) -> None:
        """Ring the candidate run that passed where its pair's base run failed."""
        g = c * 0.25
        for i in sorted(pairs):
            r, k = divmod(i, cols)
            x, y = x0 + k * (c + g), y0 + r * (c + g)
            pl.add(
                rect(
                    x - 3,
                    y - 3,
                    c + 6,
                    c + 6,
                    f"s-better {clk.fade(times[i] + 0.2, 0.2)}",
                    rx=5,
                    fill="none",
                    stroke_width=2,
                )
            )

    # task_success: 36 runs and required_sigkill: 60 runs fill side by side, each by its
    # own run order, in the same 5 s
    ts_b, ts_c = run_times(abba(TS_N), 5.0 / (2 * TS_N))
    sk_b, sk_c = run_times(abba(SK_N), 5.0 / (2 * SK_N))
    ts_pair = [max(a, b) for a, b in zip(ts_b, ts_c, strict=True)]
    sk_pair = [max(a, b) for a, b in zip(sk_b, sk_c, strict=True)]
    t_stats = max(ts_pair + sk_pair) + 0.4
    pl.add(
        text(20, 82, "task_success", "mono f-ink2"),
        text(20, 165, "base"),
        text(20, 215, "candidate"),
    )
    waffle(110, 146, ts_b, TS_FAIL, "base", 9, 18)
    waffle(110, 196, ts_c, set(), "cand", 9, 18)
    outline(110, 196, TS_FAIL, ts_pair, 9, 18)
    pl.add(
        text(330, 165, f"{TS_BASE}/{TS_N}", f"mono f-muted {clk.fade(max(ts_b))}"),
        text(330, 215, f"{TS_CAND}/{TS_N}", f"mono f-muted {clk.fade(max(ts_c))}"),
    )

    def sc(v: float) -> float:
        return 110 + (v + 0.3) / 0.6 * 220

    pl.add(
        text(20, 277, "change"),
        rect(
            sc(-0.05),
            258,
            sc(0.05) - sc(-0.05),
            26,
            f"f-band s-bandEdge {clk.fade(t_stats)}",
        ),
    )
    for v in (-0.2, 0, 0.2):
        lab = "0" if v == 0 else f"{fmt(v * 100, 0)} pp"
        pl.add(
            line(sc(v), 254, sc(v), 288, "s-muted" if v == 0 else "s-grid"),
            text(sc(v), 310, lab, "mono f-muted", FS, "middle"),
        )
    t_ci = t_stats + 0.4
    t_done = t_ci + 0.75
    pl.add(
        line(
            sc(TS_CI[0]),
            271,
            sc(TS_CI[1]),
            271,
            f"s-unsure dr {clk.draw(t_ci, 0.5)}",
            5,
            stroke_linecap="round",
            pathLength=1,
        ),
        circle(
            sc(TS_DIFF), 271, 6, f"f-plate s-unsure {clk.fade(t_ci + 0.5, 0.2)}", stroke_width=2.5
        ),
    )
    g, _ = glyph(TS_KIND, 138, 120, 26, clk.fade(t_done, 0.4))
    pl.add(text(20, 120, TS_TXT, f"f-ink bb {clk.fade(t_done, 0.4)}", 28), g)
    fx = 420
    pl.add(
        text(fx, 82, "required_sigkill", "mono f-ink2"),
        text(fx, 165, "base"),
        text(fx, 215, "candidate"),
    )
    waffle(fx + 90, 150, sk_b, SK_FAIL, "base", 15, 14)
    waffle(fx + 90, 200, sk_c, set(), "cand", 15, 14)
    outline(fx + 90, 200, SK_FAIL, sk_pair, 15, 14)
    rx0, rx1 = fx + 90, 770

    def rs(v: float) -> float:
        return rx0 + v / 300 * (rx1 - rx0)

    pl.add(
        text(fx, 277, "runs"),
        rect(rx0, 266, rx1 - rx0, 10, "f-chip", rx=5),
        line(
            rx0 + 5,
            271,
            rs(SK_N) - 5,
            271,
            f"s-cand dr {clk.draw(t_ci, 0.4)}",
            10,
            stroke_linecap="round",
            pathLength=1,
        ),
    )
    for b, v in SK_RUNS.items():
        bound = f"≤{b * 100:.0f} %"
        anchor = "middle" if v < 200 else "end"
        pl.add(
            line(rs(v), 258, rs(v), 284, "s-ink2", 1.5),
            text(rs(v), 252, bound, "mono f-muted", FS, anchor),
            text(rs(v), 306, str(v), "mono f-muted", FS, anchor),
        )
    sk_big = f"{SK_BASE / SK_N * 100:.0f} % → ≤ {SK_BOUND * 100:.1f} %"
    g, _ = glyph("improved", fx + 226, 120, 26, clk.fade(t_done, 0.4))
    pl.add(text(fx, 120, sk_big, f"f-ink bb {clk.fade(t_done, 0.4)}", 28), g)
    pl.reveal = t_done + 0.2
    return pl


def plate_g6() -> Plate:
    sp = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    rng = XorShift(59)  # the same generator and seed as the G6 sweep of #1188
    groups = []
    for v in sp:
        eff = 0.0 if v < 0.6 else -0.06 - 0.08 * (v - 0.6)
        b0 = 0.9 + 1.1 * v
        base = [b0 * math.exp(0.035 * rng.norm()) for _ in range(6)]
        cand = [b * math.exp(eff + 0.03 * rng.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], 2.015)
        groups.append((v, base, cand, m, (lo_ci, hi_ci), verdict(-hi_ci, -lo_ci, MARGIN)))
    last = groups[-1]
    desc = "task_duration, 8 speeds x 6 ABBA pairs, run speed by speed: " + "; ".join(
        f"{g[0]} m/s {fmt(pct(g[3]))} %" for g in groups
    )
    pl = Plate("Faster above 0.6 m/s", 460, desc, (last[5], f"{fmt(pct(last[3]))} %"))
    clk = pl.clk
    x0, x1, y0, y1, lo, hi = 74, 790, 80, 370, 0.95, 2.95
    step_run = 0.06

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    for t in (1.0, 1.5, 2.0, 2.5):
        pl.add(
            line(x0, ys(t), x1, ys(t), "s-grid"),
            text(x0 - 8, ys(t) + 5, f"{t:.1f} s", "mono f-muted", FS, "end"),
        )
    step = (x1 - x0) / len(sp)
    meds = []
    done = 0.0
    for k, (v, base, cand, m, ci, kind) in enumerate(groups):
        gx = x0 + (k + 0.5) * step
        tb, tc = run_times(abba(6), step_run, T0 + k * 12 * step_run)
        t_stats = max(tb + tc) + DROP + LINK
        done = columns(
            pl,
            box=(gx - 38, gx + 42, y0, y1),
            base=base,
            cand=cand,
            tb=tb,
            tc=tc,
            lo=lo,
            hi=hi,
            ci=ci,
            est=m,
            kind=kind,
            t_stats=t_stats,
            ticks=[],
            labels="none",
            r=3.4,
            pace=0.55,
            ring_dur=0.25,
        )
        meds.append((gx - 38 + 80 * 0.6 + 0.0, ys(quant(cand, 0.5)), kind, t_stats))
        g, _ = glyph(kind, gx - 4, ys(max(base + cand)) - 16, FS + 2, clk.fade(done, 0.25))
        pl.add(g, text(gx - 6, y1 + 26, f"{v:.1f}", "mono f-muted", FS, "middle"))
    # the candidate medians join up speed by speed; darker where both ends are beyond ±Δ
    for (xa, ya, ka, _), (xb, yb, kb, tb_) in itertools.pairwise(meds):
        beyond = ka == kb == "improved"
        pl.add(
            line(
                xa,
                ya,
                xb,
                yb,
                f"s-cand dr {clk.draw(tb_ + 0.15, 0.3)}",
                2,
                stroke_opacity=0.9 if beyond else 0.45,
                pathLength=1,
            )
        )
    pl.add(
        text((x0 + x1) / 2, y1 + 54, "speed (m/s)", "f-ink2", FS, "middle"),
        legend(W - 20, y1 + 54, ARMS),
    )
    pl.reveal = max(done, clk.end)
    return pl


# Design: the same 40 runs, with a slow drift and no true change, labelled two ways
D_N, D_DRIFT, D_SD = 40, 0.004, 0.03
_DR = XorShift(83)
D_VALS = [0.42 * math.exp(D_DRIFT * k + D_SD * _DR.norm()) for k in range(D_N)]
D_ARMS = {"ABBA": "".join(abba(D_N // 2)), "blocked": "A" * (D_N // 2) + "B" * (D_N // 2)}


def design_shift(arms: str) -> tuple[float, tuple[float, float]]:
    """Return the log shift B/A and its 90 % t interval for one labelling of D_VALS."""
    la = [math.log(v) for v, a in zip(D_VALS, arms, strict=True) if a == "A"]
    lb = [math.log(v) for v, a in zip(D_VALS, arms, strict=True) if a == "B"]
    if arms == D_ARMS["ABBA"]:  # paired: the two runs of each pair are back to back
        diffs = [
            math.log(D_VALS[2 * j + arms[2 * j : 2 * j + 2].index("B")])
            - math.log(D_VALS[2 * j + arms[2 * j : 2 * j + 2].index("A")])
            for j in range(D_N // 2)
        ]
        m, lo, hi = t_ci(diffs, 1.729)  # t(0.95, 19)
        return m, (lo, hi)
    m = mean(lb) - mean(la)
    h = 1.686 * math.sqrt(sd(la) ** 2 / len(la) + sd(lb) ** 2 / len(lb))  # t(0.95, 38)
    return m, (m - h, m + h)


D_SHIFT = {name: design_shift(arms) for name, arms in D_ARMS.items()}


def plate_design() -> Plate:
    kinds = {name: verdict(*oriented(ci), MARGIN) for name, (_, ci) in D_SHIFT.items()}
    if kinds["blocked"] != "regressed" or kinds["ABBA"] not in {"equiv", "small"}:
        msg = f"the design plate needs a false regression when blocked, got {kinds}"
        raise ValueError(msg)
    desc = (
        f"The same 40 runs, drifting {D_DRIFT * 100:.1f} % per run with no true change, "
        f"labelled two ways. ABBA pairs: {fmt(pct(D_SHIFT['ABBA'][0]))} %, no change. "
        f"Blocked (all base, then all candidate): {fmt(pct(D_SHIFT['blocked'][0]))} %, "
        "a false regression."
    )
    pl = Plate("Blocked order invents a regression", 500, desc)
    clk = pl.clk
    px, qx = 80, 600
    step = (qx - px) / D_N
    lo, hi = axis_range(D_VALS, 0.12)
    done = 0.0
    for row, (name, arms) in enumerate(D_ARMS.items()):
        y0 = 92 + row * 196
        y1 = y0 + 140

        def ys(v: float, y0: float = y0, y1: float = y1) -> float:
            return y1 - (v - lo) / (hi - lo) * (y1 - y0)

        def xs(k: float) -> float:
            return px + (k + 0.5) * step

        times = [T0 + k * STEP for k in range(D_N)]
        t_stats = times[-1] + DROP + LINK
        la = [v for v, a in zip(D_VALS, arms, strict=True) if a == "A"]
        lb = [v for v, a in zip(D_VALS, arms, strict=True) if a == "B"]
        bmed = quant(la, 0.5)
        est, ci = D_SHIFT[name]
        kind = kinds[name]
        mark, _, _ = VERDICT[kind]
        pl.add(text(20, y0 - 10, name, "f-ink b"))
        for t in nice_ticks(lo, hi, 3):
            pl.add(
                line(px, ys(t), qx + 70, ys(t), "s-grid"),
                text(px - 7, ys(t) + 5, f"{t:.2f}", "mono f-muted", FS, "end"),
            )
        top, bot = ys(bmed * math.exp(MARGIN)), ys(bmed * math.exp(-MARGIN))
        pl.add(
            rect(px, top, qx + 70 - px, bot - top, f"f-band s-bandEdge {clk.fade(t_stats + 0.35)}"),
            line(
                xs(0),
                ys(0.42),
                xs(D_N - 1),
                ys(0.42 * math.exp(D_DRIFT * (D_N - 1))),
                f"s-muted dr {clk.draw(times[0], times[-1] - times[0] + DROP)}",
                1.5,
                pathLength=1,
            ),
        )
        if name == "ABBA":
            for j in range(D_N // 2):
                ia = 2 * j + arms[2 * j : 2 * j + 2].index("A")
                ib = 2 * j + arms[2 * j : 2 * j + 2].index("B")
                better = D_VALS[ib] < D_VALS[ia]
                pl.add(
                    line(
                        xs(ia),
                        ys(D_VALS[ia]),
                        xs(ib),
                        ys(D_VALS[ib]),
                        f"s-{'better' if better else 'worse'} dr "
                        f"{clk.draw(times[2 * j + 1] + DROP, LINK)}",
                        1.6,
                        stroke_opacity=0.75,
                        pathLength=1,
                    )
                )
        rings = []
        for k, (v, a) in enumerate(zip(D_VALS, arms, strict=True)):
            tok = "base" if a == "A" else "cand"
            pl.add(circle(xs(k), ys(v), 5, f"f-{tok} s-plate {clk.drop(times[k])}", stroke_width=1))
            rings.append(
                circle(xs(k), ys(v), 6, f"s-ink ring {clk.ring(times[k] + DROP)}", stroke_width=1.5)
            )
        for vals, tok in ((la, "base"), (lb, "cand")):
            ks = [k for k, a in enumerate(arms) if a == ("A" if tok == "base" else "B")]
            ym = ys(quant(vals, 0.5))
            g = clk.grow(t_stats, 0.3)
            pl.add(
                line(xs(min(ks)), ym, xs(max(ks)), ym, f"s-plate {g}", 7, stroke_linecap="round"),
                line(xs(min(ks)), ym, xs(max(ks)), ym, f"s-{tok} {g}", 3.5, stroke_linecap="round"),
            )
        bx = qx + 30
        y_top, y_bot = sorted((ys(bmed * math.exp(ci[0])), ys(bmed * math.exp(ci[1]))))
        t_ci = t_stats + 0.7
        pl.add(
            el(
                "path",
                d=f"M{num(bx - 7)} {num(y_bot)}H{num(bx)}V{num(y_top)}H{num(bx - 7)}",
                cls=f"s-{mark} dr {clk.draw(t_ci, 0.45)}",
                fill="none",
                stroke_width=3,
                stroke_linecap="round",
                stroke_linejoin="round",
                pathLength=1,
            ),
            line(
                bx - 9,
                ys(bmed * math.exp(est)),
                bx + 3,
                ys(bmed * math.exp(est)),
                f"s-{mark} {clk.fade(t_ci + 0.45, 0.2)}",
                3,
                stroke_linecap="round",
            ),
            *rings,
        )
        done = t_ci + 0.7
        big = f"{fmt(pct(est))} %"
        g, _ = glyph(kind, W - 20 - 22, y0 + 64, 26, clk.fade(done, 0.4))
        pl.add(text(W - 50, y0 + 64, big, f"f-ink bb {clk.fade(done, 0.4)}", 26, "end"), g)
    pl.add(
        line(px, 450, qx, 450, "s-muted"),
        el("path", d=f"M{qx} 445L{qx + 9} 450L{qx} 455Z", cls="f-muted"),
        text(px, 476, "run order", "f-muted"),
        legend(W - 20, 476, ARMS),
    )
    pl.reveal = done
    return pl


PLATES = {
    "p1_scorecard.svg": plate_g1,
    "p2_forest.svg": plate_g2,
    "p3_estimation.svg": plate_g3,
    "p4_inconclusive.svg": plate_small,
    "p5_waffle.svg": plate_g5,
    "p6_sweep.svg": plate_g6,
    "p7_design.svg": plate_design,
}


def facts() -> dict[str, str]:
    """Return every number that the PR captions quote, from the same data as the plates."""
    p = pct
    rows = forest_rows()
    return {
        "planning_time": f"{fmt(p(EST))} % 90% BCa [{fmt(p(C90[0]))}, {fmt(p(C90[1]))}]",
        "pairs_faster": f"{sum(q.cand < q.base for q in PAIRS)}/{len(PAIRS)}",
        "tracking_error": f"{fmt(p(TRACK_EST))} % 90% BCa [{fmt(p(TRACK_C90[0]))}, "
        f"{fmt(p(TRACK_C90[1]))}]",
        "small": f"{fmt(p(SMALL_EST))} % 90% t [{fmt(p(SMALL_CI[0]))}, {fmt(p(SMALL_CI[1]))}]",
        "task_success": f"{TS_TXT} Newcombe 90% {TS_CI_TXT} {TS_KIND} fail pair {sorted(TS_FAIL)}",
        "sigkill": f"{SK_BASE}/{SK_N}->{SK_CAND}/{SK_N} bound {SK_BOUND * 100:.1f} % "
        f"runs {SK_RUNS} pairs {sorted(SK_FAIL)}",
        "forest": "; ".join(f"{r[0]} {fmt(p(r[4]))}" for r in rows),
        "design": "; ".join(
            f"{n} {fmt(p(m))} % [{fmt(p(c[0]))}, {fmt(p(c[1]))}]" for n, (m, c) in D_SHIFT.items()
        ),
    }


def main() -> None:
    if "--facts" in sys.argv:
        for k, v in facts().items():
            sys.stdout.write(f"{k}: {v}\n")
        return
    for name, make in PLATES.items():
        pl = make()
        (OUT / name).write_text(pl.render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}: draw ends at {pl.clk.end:.2f} s\n")


if __name__ == "__main__":
    main()
