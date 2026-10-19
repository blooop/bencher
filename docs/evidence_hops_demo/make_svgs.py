"""Write the literature-faithful animated statistics plates as standalone SVG files.

This is the unconstrained counterpart of ``docs/evidence_svg_demo``: the same synthetic
data and the same dot style, but here the animation carries the method. Each plate
follows a method from the literature (see README.md next to this file):

* Hypothetical outcome plots (HOPs): one draw per frame, 400 ms per frame, no trail.
* Cumming's dance of the confidence intervals and p-values: replications arrive one at a
  time beside the true effect.
* The bootstrap build-up of the VIT tools: resample, recompute, drop the statistic into
  the growing sampling distribution, then trim the tails to an interval.

Every plate also draws its static companion (the final interval) so a single still frame
still carries the finding. The data are synthetic and seeded; the script uses only the
standard library:

    python docs/evidence_hops_demo/make_svgs.py

Each SVG carries a light and a dark palette (``prefers-color-scheme``). The animation is
CSS keyframes on one shared loop per file. ``prefers-reduced-motion`` stops it and shows
the static companion plus the final state.
"""

# ruff: noqa: PLR2004, RUF001, S311
# PLR2004: a plot is mostly literal coordinates. RUF001: the labels use the real minus
# sign on purpose. S311: the draws are a seeded simulation, not cryptography.

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

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


HOP_STEP = 0.4  # s per hypothetical outcome: Hullman et al. 2015, Kale et al. 2019
N_HOPS = 40

BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
.fr{{opacity:0}}
.rmonly{{display:none}}
@media (prefers-reduced-motion:reduce){{
.fr{{animation:none!important;opacity:0;transform:none!important}}
.fr.keep{{opacity:1}}.rmonly{{display:inline}}}}
"""


class Clock:
    """Visibility windows on one shared loop: pure CSS keyframes, no JS.

    ``win(t0, t1)`` returns a class that shows an element from t0 to t1 seconds of the
    loop and hides it otherwise. Elements marked ``keep`` stay visible when motion is off,
    so the reduced-motion still is the final state of the animation.
    """

    def __init__(self, loop: float) -> None:
        self.loop = loop
        self.css = ""
        self._names: dict[tuple[float, float], str] = {}

    def _pc(self, t: float) -> float:
        return min(max(t / self.loop * 100, 0.0), 100.0)

    def win(self, t0: float, t1: float | None = None, keep: bool = False) -> str:
        t1 = self.loop if t1 is None else t1
        key = (round(t0, 3), round(t1, 3))
        name = self._names.get(key)
        if name is None:
            name = f"w{len(self._names)}"
            self._names[key] = name
            p0, p1, e = self._pc(t0), self._pc(t1), 0.01
            steps = []
            if p0 > 0:
                steps.append(f"0%,{p0 - e:.3f}%{{opacity:0}}")
            if p1 < 100:
                steps.append(f"{p0:.3f}%,{p1 - e:.3f}%{{opacity:1}}{p1:.3f}%,100%{{opacity:0}}")
            else:
                steps.append(f"{p0:.3f}%,100%{{opacity:1}}")
            self.css += (
                f"@keyframes {name}{{{''.join(steps)}}}"
                f".{name}{{animation:{name} {self.loop:.2f}s linear infinite}}"
            )
        return f"fr {name}" + (" keep" if keep else "")

    def drop(self, t0: float, t1: float, dy: float) -> str:
        """Return a class that appears at t0, falls dy px into place by t1, then stays."""
        name = f"d{len(self._names)}"
        self._names[(-len(self._names) - 1.0, 0.0)] = name
        p0, p1, e = self._pc(t0), self._pc(t1), 0.01
        self.css += (
            f"@keyframes {name}{{0%,{p0 - e:.3f}%{{opacity:0;transform:translateY({dy:.1f}px)}}"
            f"{p0:.3f}%{{opacity:1;transform:translateY({dy:.1f}px)}}"
            f"{p1:.3f}%,100%{{opacity:1;transform:translateY(0)}}}}"
            f".{name}{{animation:{name} {self.loop:.2f}s ease-in infinite}}"
        )
        return f"fr {name} keep"


class Plate:
    def __init__(
        self,
        title: str,
        height: float,
        desc: str,
        loop: float,
        big: tuple[str, str] | None = None,
    ) -> None:
        self.title, self.height, self.desc, self.big = title, height, desc, big
        self.parts: list[str] = []
        self.clock = Clock(loop)

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def at(self, body: str, t0: float, t1: float | None = None, keep: bool = False) -> str:
        """Wrap body so it shows only from t0 to t1 of the loop."""
        return el("g", body, cls=self.clock.win(t0, t1, keep))

    @staticmethod
    def _palette(pal: dict[str, str]) -> str:
        return "".join(f".f-{k}{{fill:{v}}}.s-{k}{{stroke:{v}}}" for k, v in pal.items())

    def render(self) -> str:
        h = num(float(self.height))
        css = (
            BASE_CSS
            + self._palette(LIGHT)
            + "\n@media (prefers-color-scheme:dark){"
            + self._palette(DARK)
            + "}\n"
            + self.clock.css
        )
        head = [
            rect(0.5, 0.5, W - 1, self.height - 1, "f-plate s-rule", rx=6),
            text(20, 40, self.title, "f-ink bb", 23),
        ]
        if self.big:
            kind, s = self.big
            gw = 30 * 0.74
            g, _ = glyph(kind, W - 20 - gw, 42, 30)
            head += [g, text(W - 30 - gw, 42, s, "f-ink bb", 30, "end")]
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{''.join(head)}{''.join(self.parts)}</svg>\n"
        )


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
C90 = (quant(BOOTS, 0.05), quant(BOOTS, 0.95))
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
TRACK_C90 = (quant(TRACK_BOOTS, 0.05), quant(TRACK_BOOTS, 0.95))


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


# ---------------------------------------------------------------- statistics


def betainc(a: float, b: float, x: float) -> float:
    """Return the regularised incomplete beta I_x(a, b) by Lentz's continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1 - betainc(b, a, 1 - x)
    lg = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lg + a * math.log(x) + b * math.log1p(-x)) / a
    tiny = 1e-30
    c, d = 1.0, 1.0 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        for aa in (
            m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m)),
            -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1)),
        ):
            d = 1 + aa * d
            d = 1 / (d if abs(d) > tiny else tiny)
            c = 1 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1) < 1e-12:
            break
    return front * h


def p_paired(log_diffs: list[float]) -> float:
    """Return the two-sided p value of the paired t test of the log differences."""
    n = len(log_diffs)
    t = mean(log_diffs) / (sd(log_diffs) / math.sqrt(n))
    df = n - 1
    return betainc(df / 2, 0.5, df / (df + t * t))


def p_text(p: float) -> str:
    return "p<.001" if p < 0.001 else f"p={p:.3f}"[:7].replace("0.", ".")


T90 = {5: 2.015, 19: 1.729}  # two-sided 90 % t quantiles


def t_draws(rng: random.Random, est: float, se: float, df: int, n: int) -> list[float]:
    """Draw n plausible values of an effect from its t sampling distribution."""
    return [
        est + se * rng.gauss(0, 1) / math.sqrt(rng.gammavariate(df / 2, 2) / df) for _ in range(n)
    ]


def wilson(k: int, n: int, z: float) -> tuple[float, float]:
    p, den = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def newcombe(k1: int, n1: int, k2: int, n2: int, z: float = 1.645) -> tuple[float, float]:
    """Return Newcombe's hybrid score interval for p2 - p1."""
    p1, p2 = k1 / n1, k2 / n2
    (l1, u1), (l2, u2) = wilson(k1, n1, z), wilson(k2, n2, z)
    d = p2 - p1
    return d - math.hypot(p2 - l2, u1 - p1), d + math.hypot(u2 - p2, p1 - l1)


def cat(d: float, lower_better: bool = True) -> str:
    """Return the colour token of one draw: beyond the margin either way, or inside it."""
    g = -d if lower_better else d
    return "better" if g > MARGIN else "worse" if g < -MARGIN else "ink2"


TXT = {"better": "tbetter", "worse": "tworse", "ink2": "ink2", "unsure": "tunsure"}


def axis_range(vals: list[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return lo - span * pad, hi + span * pad


def dot_path(pts: list[tuple[float, float]], r: float) -> str:
    """Return one path that draws a circle of radius r at every point (small files)."""
    return "".join(
        f"M{num(x - r)} {num(y)}a{num(r)} {num(r)} 0 1 0 {num(2 * r)} 0"
        f"a{num(r)} {num(r)} 0 1 0 {num(-2 * r)} 0"
        for x, y in pts
    )


def counter(pl: Plate, x: float, y: float, n: int, step: float, t_start: float = 0) -> None:
    """Number each frame, as the HOPs of Hullman et al. do, so a reader knows it is one draw."""
    for k in range(n):
        t0 = t_start + k * step
        pl.add(pl.at(text(x, y, f"draw {k + 1} / {n}", "mono f-muted", FS, "end"), t0, t0 + step))


# ---------------------------------------------------------------- plates 1 and 2: HOPs


def _shift_hops(
    title: str,
    desc: str,
    pairs: list[Pair],
    draws: list[float],
    dist: list[float],
    ci: tuple[float, float],
    est: float,
    kind: str,
) -> Plate:
    """HOPs of the candidate median: each frame one plausible shift applied to the base median.

    The dots are the observed runs and never move. Right: the same uncertainty as a static
    quantile dotplot (Kay et al. 2016) of 20 dots with the 90 % CI, on the same axis.
    """
    loop = len(draws) * HOP_STEP
    pl = Plate(title, 480, desc, loop, (kind, f"{fmt(pct(est))} %"))
    base, cand = [p.base for p in pairs], [p.cand for p in pairs]
    bmed = quant(base, 0.5)
    shifted = [bmed * math.exp(d) for d in dist]
    lo, hi = axis_range([*base, *cand, quant(shifted, 0.002), quant(shifted, 0.998)], 0.06)
    x0, x1, y0, y1 = 20, 560, 84, 400

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    px = x0 + 50
    wid = x1 - px
    cb, cc = px + wid * 0.25, px + wid * 0.6
    for t in nice_ticks(lo, hi, 4):
        pl.add(
            line(px, ys(t), x1, ys(t), "s-grid"),
            text(px - 7, ys(t) + 5, f"{t:.2f} s", "mono f-muted", FS, "end"),
        )
    top, bot = ys(bmed * math.exp(MARGIN)), ys(bmed * math.exp(-MARGIN))
    pl.add(rect(px + 2, top, x1 - px - 4, bot - top, "f-band s-bandEdge", stroke_width=1))
    r = 4.5
    pb, pc = [ys(v) for v in base], [ys(v) for v in cand]
    ob, oc = swarm(pb, r), swarm(pc, r)
    for i in range(len(base)):
        better = cand[i] < base[i]
        pl.add(
            line(
                cb + ob[i],
                pb[i],
                cc + oc[i],
                pc[i],
                "s-cand" if better else "s-worse",
                1.2,
                stroke_opacity=0.3 if better else 0.6,
            )
        )
    pl.add(
        *(
            circle(cb + o, p, r, "f-base s-plate", stroke_width=1)
            for o, p in zip(ob, pb, strict=True)
        )
    )
    pl.add(
        *(
            circle(cc + o, p, r, "f-cand s-plate", stroke_width=1)
            for o, p in zip(oc, pc, strict=True)
        )
    )
    hwb = min(max(abs(o) for o in ob) + r + 5, wid * 0.15)
    hwc = min(max(abs(o) for o in oc) + r + 5, wid * 0.15)

    def bar(cx: float, y: float, hw: float, tok: str) -> str:
        return line(cx - hw, y, cx + hw, y, "s-plate", 9, stroke_linecap="round") + line(
            cx - hw, y, cx + hw, y, f"s-{tok}", 5, stroke_linecap="round"
        )

    pl.add(bar(cb, ys(bmed), hwb, "base"))

    def outcome(d: float, tok: str) -> str:
        y = ys(bmed * math.exp(d))
        return (
            line(cb + hwb + 4, ys(bmed), cc - hwc - 4, y, f"s-{tok}", 2.5)
            + bar(cc, y, hwc, tok)
            + text(cc + hwc + 10, y + 5, f"{fmt(pct(d))} %", f"f-{TXT[tok]} b", FS)
        )

    for k, d in enumerate(draws):
        pl.add(pl.at(outcome(d, cat(d)), k * HOP_STEP, (k + 1) * HOP_STEP))
    pl.add(el("g", outcome(est, VERDICT[kind][0]), cls="rmonly"))
    pl.add(text(px, 70, "one plausible shift per frame, 0.4 s each", "f-ink2"))
    counter(pl, x1, y1 + 50, len(draws), HOP_STEP)
    for cx, name, n in ((cb, "base", len(base)), (cc, "candidate", len(cand))):
        pl.add(
            text(cx, y1 + 26, name, "f-ink2", FS, "middle"),
            text(cx, y1 + 45, f"n={n}", "mono f-muted", FS, "middle"),
        )
    # static companion: a quantile dotplot (Kay et al. 2016) of the same distribution, on
    # a zoomed axis of the shift, with the 90 % CI; a tick marks the frame's draw on it
    qx = 590
    pl.add(line(qx - 12, y0 - 6, qx - 12, y1, "s-rule"))
    pl.add(text(qx, 70, "20 quantile dots", "f-ink2"))
    qs = [pct(quant(dist, (i + 0.5) / 20)) for i in range(20)]
    tails = [pct(quant(dist, 0.01)), pct(quant(dist, 0.99))]
    qlo, qhi = axis_range([*tails, -6.0, 6.0], 0.06)

    def yq(v: float) -> float:
        return y1 - (v - qlo) / (qhi - qlo) * (y1 - y0)

    for t in nice_ticks(qlo, qhi, 4):
        pl.add(
            line(qx + 44, yq(t), 780, yq(t), "s-grid"),
            text(qx + 38, yq(t) + 5, f"{t:+.0f} %" if t else "0", "mono f-muted", FS, "end"),
        )
    pl.add(
        rect(qx + 46, yq(5), 780 - qx - 48, yq(-5) - yq(5), "f-band s-bandEdge", stroke_width=1),
        line(qx + 46, yq(0), 780, yq(0), "s-ink2", 1),
    )
    dot_x0, room = qx + 86, 780 - qx - 92
    dd = 11.0
    while True:
        stacks: dict[int, int] = {}
        for q in qs:
            key = round(yq(q) / dd)
            stacks[key] = stacks.get(key, 0) + 1
        if max(stacks.values()) * dd <= room:
            break
        dd *= 0.9
    stacks = {}
    for q in qs:
        key = round(yq(q) / dd)
        j = stacks.get(key, 0)
        stacks[key] = j + 1
        tok = cat(math.log1p(q / 100))
        pl.add(circle(dot_x0 + j * dd, key * dd, dd / 2 - 0.6, f"f-{tok} s-plate", stroke_width=1))
    mark = VERDICT[kind][0]
    y_lo, y_hi = sorted((yq(pct(ci[0])), yq(pct(ci[1]))))
    bx = qx + 62
    pl.add(
        el(
            "path",
            d=f"M{num(bx + 7)} {num(y_lo)}H{num(bx)}V{num(y_hi)}H{num(bx + 7)}",
            cls=f"s-{mark}",
            fill="none",
            stroke_width=3,
            stroke_linecap="round",
        ),
        line(bx - 3, yq(pct(est)), bx + 9, yq(pct(est)), f"s-{mark}", 3),
        text(qx, y1 + 26, "90 % CI", "f-ink2"),
        text(qx, y1 + 45, f"{fmt(pct(ci[0]))}, {fmt(pct(ci[1]))} %", "mono f-muted"),
    )
    for k, d in enumerate(draws):
        y = yq(pct(d))
        tri = f"M{num(bx + 12)} {num(y)}l9 -6v12Z"
        pl.add(pl.at(el("path", d=tri, cls=f"f-{cat(d)}"), k * HOP_STEP, (k + 1) * HOP_STEP))
    return pl


def plate_h1() -> Plate:
    desc = (
        "planning_time, 20 paired runs. Each frame shows one bootstrap draw of the shift as a "
        f"candidate median; all 40 draws are faster by more than 5 %. 90 % CI "
        f"{fmt(pct(C90[0]))} to {fmt(pct(C90[1]))} %."
    )
    return _shift_hops(
        "Every plausible shift is faster",
        desc,
        PAIRS,
        BOOTS[:N_HOPS],
        BOOTS,
        C90,
        EST,
        verdict(-C90[1], -C90[0], MARGIN),
    )


# n = 6 pairs of a metric with a small true change (-3 %); plate 4 replicates this run
SMALL_EFFECT, SMALL_SD = math.log(0.97), 0.07
_SR = XorShift(100)
SMALL: list[Pair] = []
for _p in range(6):
    _b = 0.42 * SHARD_SPEED[_p % 4] * math.exp(0.18 * _SR.norm())
    SMALL.append(Pair(_p % 4, _p, _b, _b * math.exp(SMALL_EFFECT + SMALL_SD * _SR.norm()), "AB"))
SMALL_LD = [math.log(p.cand / p.base) for p in SMALL]


def plate_h2() -> Plate:
    est, lo_ci, hi_ci = t_ci(SMALL_LD, T90[5])
    se = (hi_ci - lo_ci) / 2 / T90[5]
    rng = random.Random(72)
    draws = t_draws(rng, est, se, 5, N_HOPS)
    dist = t_draws(rng, est, se, 5, 4000)
    n_in = sum(cat(d) == "ink2" for d in draws)
    n_b = sum(cat(d) == "better" for d in draws)
    n_w = len(draws) - n_in - n_b
    desc = (
        f"6 paired runs. Each frame is one plausible shift from the t distribution: {n_b} of 40 "
        f"draws are faster by more than 5 %, {n_in} are inside ±5 %, {n_w} slower by more. "
        f"90 % CI {fmt(pct(lo_ci))} to {fmt(pct(hi_ci))} %: inconclusive."
    )
    return _shift_hops(
        "Six runs: the draws disagree",
        desc,
        SMALL,
        draws,
        dist,
        (lo_ci, hi_ci),
        est,
        verdict(-hi_ci, -lo_ci, MARGIN),
    )


# ---------------------------------------------------------------- plate 3: HOPs of rates


def plate_h3() -> Plate:
    kb, kc, n = 17, 18, 18
    lo_d, hi_d = newcombe(kb, n, kc, n)
    rng = random.Random(83)
    # Jeffreys posterior of each rate: Beta(k + 1/2, n - k + 1/2)
    draws = [
        (rng.betavariate(kb + 0.5, n - kb + 0.5), rng.betavariate(kc + 0.5, n - kc + 0.5))
        for _ in range(4000)
    ]
    p_sup = sum(c > b for b, c in draws) / len(draws)
    desc = (
        f"task_success, base 17/18 and candidate 18/18. Each frame is one plausible pair of "
        f"rates (Jeffreys posterior draws). The candidate is higher in {p_sup:.0%} of draws. "
        f"Newcombe 90 % CI of the difference {fmt(lo_d * 100)} to {fmt(hi_d * 100)} pp."
    )
    loop = N_HOPS * HOP_STEP
    pl = Plate("18 of 18 could be luck", 390, desc, loop, ("unsure", f"{fmt(100 / 18)} pp"))
    # observed waffles (static)
    pl.add(text(30, 76, "observed runs", "f-ink2"))
    c, g = 17.0, 4.0
    for row, (name, k, tok) in enumerate((("base", kb, "base"), ("candidate", kc, "cand"))):
        y = 108 + row * 72
        pl.add(text(30, y - 8, f"{name}  {k}/{n}", "f-ink2"))
        for i in range(n):
            rr, cc = divmod(i, 9)
            x, yy = 30 + cc * (c + g), y + rr * (c + g)
            ok = i < k
            pl.add(
                rect(
                    x,
                    yy,
                    c,
                    c,
                    f"f-{tok}" if ok else "f-plate s-worse",
                    rx=3,
                    stroke_width=None if ok else 2.5,
                )
            )
    # HOPs: one plausible pair of rates per frame, as bars from 0
    bx0, bx1 = 280, 690

    def bxs(p: float) -> float:
        return bx0 + p * (bx1 - bx0)

    pl.add(text(bx0, 76, "plausible rates, one pair per frame", "f-ink2"))
    for t in (0.0, 0.5, 1.0):
        pl.add(
            line(bxs(t), 86, bxs(t), 222, "s-grid"),
            text(bxs(t), 240, f"{t:.0%}", "mono f-muted", FS, "middle"),
        )
    rows = ((108, "f-base", kb), (180, "f-cand", kc))
    for y, _, k in rows:
        pl.add(line(bxs(k / n), y - 6, bxs(k / n), y + 30, "s-ink", 2))  # observed rate
    # difference axis (pp): one draw per frame above, the static Newcombe CI below
    dx0, dx1, dlo, dhi = 120, 760, -30.0, 40.0

    def dxs(v: float) -> float:
        return dx0 + (v - dlo) / (dhi - dlo) * (dx1 - dx0)

    pl.add(
        line(dxs(0), 262, dxs(0), 330, "s-ink2", 1.5),
        text(30, 283, "this draw", "f-ink2"),
        text(30, 318, "90 % CI", "f-ink2"),
    )
    for t in (-20, -10, 0, 10, 20, 30, 40):
        pl.add(text(dxs(t), 352, f"{t:+d}" if t else "0", "mono f-muted", FS, "middle"))
    pl.add(text((dx0 + dx1) / 2, 376, "candidate − base (pp)", "f-ink2", FS, "middle"))
    pl.add(
        line(dxs(lo_d * 100), 313, dxs(hi_d * 100), 313, "s-unsure", 4, stroke_linecap="round"),
        line(dxs(100 / 18), 305, dxs(100 / 18), 321, "s-unsure", 3),
    )
    for k, (pb_, pc_) in enumerate(draws[:N_HOPS]):
        diff = (pc_ - pb_) * 100
        tok = "better" if diff > 0 else "worse"
        body = "".join(
            rect(bx0, y, bxs(p) - bx0, 24, cls, rx=2)
            + text(bxs(p) + 8, y + 18, f"{p:.0%}", "f-ink b")
            for (y, cls, _), p in zip(rows, (pb_, pc_), strict=True)
        )
        body += circle(dxs(diff), 278, 7, f"f-{tok} s-plate", stroke_width=1.5)
        body += text(dxs(diff) + 12, 284, f"{fmt(diff)} pp", f"f-{TXT[tok]} b")
        pl.add(pl.at(body, k * HOP_STEP, (k + 1) * HOP_STEP))
    counter(pl, 780, 76, N_HOPS, HOP_STEP)
    pl.add(
        el(
            "g",
            "".join(rect(bx0, y, bxs(k / n) - bx0, 24, cls, rx=2) for y, cls, k in rows),
            cls="rmonly",
        )
    )
    return pl


# ---------------------------------------------------------------- plate 4: dance of the CIs

DANCE_STEP = 0.6


def plate_h4() -> Plate:
    rng = random.Random(97)
    reps = 20
    loop = reps * DANCE_STEP + 5
    cols = []
    for n in (6, 20):
        rows = []
        for _ in range(reps):
            ld = [SMALL_EFFECT + SMALL_SD * rng.gauss(0, 1) for _ in range(n)]
            m, a, b = t_ci(ld, T90[n - 1])
            rows.append((m, a, b, p_paired(ld), verdict(-b, -a, MARGIN)))
        cols.append((n, rows))
    ps = [[r[3] for r in rows] for _, rows in cols]
    desc = (
        "20 replications of the same experiment, true shift −3 %, 90 % CIs and paired t-test "
        f"p values. n=6: {p_text(min(ps[0]))} to {p_text(max(ps[0]))}; n=20: "
        f"{p_text(min(ps[1]))} to {p_text(max(ps[1]))}."
    )
    pl = Plate("Same experiment, twenty replications", 500, desc, loop)
    vlo, vhi = -16.0, 10.0
    y0, step = 96, 16.0
    for ci_, (n, rows) in enumerate(cols):
        cx0 = 20 + ci_ * 395
        ax0, ax1 = cx0 + 8, cx0 + 300

        def xs(v: float, ax0: float = ax0, ax1: float = ax1) -> float:
            return ax0 + (v - vlo) / (vhi - vlo) * (ax1 - ax0)

        ybot = y0 + reps * step
        pl.add(
            rect(
                xs(-5), y0 - 10, xs(5) - xs(-5), ybot - y0 + 4, "f-band s-bandEdge", stroke_width=1
            ),
            line(xs(0), y0 - 10, xs(0), ybot - 6, "s-ink2", 1),
            line(
                xs(pct(SMALL_EFFECT)),
                y0 - 14,
                xs(pct(SMALL_EFFECT)),
                ybot - 4,
                "s-ink",
                1.5,
                stroke_dasharray="5 4",
            ),
            text(cx0 + 8, 72, f"n = {n} pairs", "f-ink b"),
            text(xs(pct(SMALL_EFFECT)) + 6, 72, f"true {fmt(pct(SMALL_EFFECT), 0)} %", "f-ink2"),
        )
        for t in (-15, -10, -5, 0, 5, 10):
            pl.add(text(xs(t), ybot + 20, f"{t:+d}" if t else "0", "mono f-muted", FS, "middle"))
        pl.add(text((ax0 + ax1) / 2, ybot + 42, "shift (%)", "f-ink2", FS, "middle"))
        for k, (m, a, b, p, kind) in enumerate(rows):
            y = y0 + k * step
            mark = VERDICT[kind][0]
            t0 = k * DANCE_STEP
            body = (
                line(xs(pct(a)), y, xs(pct(b)), y, f"s-{mark}", 3, stroke_linecap="round")
                + circle(xs(pct(m)), y, 4, f"f-{mark} s-plate", stroke_width=1)
                + text(ax1 + 12, y + 5, p_text(p), "mono f-ink bb" if p < 0.05 else "mono f-muted")
            )
            pl.add(pl.at(body, t0, keep=True))
            pl.add(
                pl.at(
                    circle(xs(pct(m)), y, 8, "s-ink", fill="none", stroke_width=2),
                    t0,
                    t0 + DANCE_STEP,
                )
            )
        pv = [r[3] for r in rows]
        pl.add(
            pl.at(
                text(cx0 + 8, ybot + 68, f"{p_text(min(pv))} to {p_text(max(pv))}", "f-ink b"),
                reps * DANCE_STEP,
                keep=True,
            )
        )
    return pl


# ---------------------------------------------------------------- plate 5: bootstrap


def plate_h5() -> Plate:
    rng = random.Random(5)
    n = len(LOG_DIFF)
    slow, fast, slow_step, fast_step = 6, 94, 1.6, 0.12
    t_end = slow * slow_step + fast * fast_step
    loop = t_end + 5.5
    resamples = [[rng.randrange(n) for _ in range(n)] for _ in range(slow + fast)]
    means = [mean([LOG_DIFF[i] for i in idx]) for idx in resamples]
    c_lo, c_hi = quant(means, 0.05), quant(means, 0.95)
    desc = (
        "planning_time, the 20 paired shifts. Each frame resamples the 20 with replacement, "
        "recomputes the mean shift and drops it into the bootstrap distribution. After 100 "
        f"resamples the tails are trimmed: 90 % CI {fmt(pct(c_lo))} to {fmt(pct(c_hi))} %."
    )
    pl = Plate("Resample, recompute, repeat", 560, desc, loop, ("improved", f"{fmt(pct(EST))} %"))
    vals = [pct(v) for v in LOG_DIFF]
    lo, hi = axis_range(vals, 0.06)
    ax0, ax1 = 70, 770

    def xs(v: float) -> float:
        return ax0 + (v - lo) / (hi - lo) * (ax1 - ax0)

    r = 5.0
    y1c, y2c, y3b = 122.0, 222.0, 462.0
    for t in nice_ticks(lo, hi, 5):
        pl.add(
            line(xs(t), 90, xs(t), y3b + 6, "s-grid"),
            text(xs(t), y3b + 30, f"{t:.0f}", "mono f-muted", FS, "middle"),
        )
    pl.add(text((ax0 + ax1) / 2, y3b + 54, "shift, candidate vs base (%)", "f-ink2", FS, "middle"))
    pl.add(
        text(20, 84, "sample: 20 paired shifts", "f-ink2"),
        text(20, 184, "resample with replacement", "f-ink2"),
        text(20, 284, "mean of each resample", "f-ink2"),
    )
    px = [xs(v) for v in vals]
    off = swarm(px, r)
    pos = [(x, y1c + o) for x, o in zip(px, off, strict=True)]
    pl.add(*(circle(x, y, r, "f-cand s-plate", stroke_width=1) for x, y in pos))
    pl.add(line(xs(pct(EST)), y1c - 22, xs(pct(EST)), y1c + 22, "s-ink", 3))
    # bootstrap distribution positions: stacked dots on the same axis
    dd = 2 * r + 0.6
    stacks: dict[int, int] = {}
    slots = []
    for m in means:
        key = round(xs(pct(m)) / dd)
        j = stacks.get(key, 0)
        stacks[key] = j + 1
        slots.append((key * dd, y3b - r - j * dd))
    for k, idx in enumerate(resamples):
        is_slow = k < slow
        t0 = k * slow_step if is_slow else slow * slow_step + (k - slow) * fast_step
        dur = slow_step if is_slow else fast_step
        rv = [vals[i] for i in idx]
        roff = swarm([xs(v) for v in rv], r)
        rpts = [(xs(v), y2c + o) for v, o in zip(rv, roff, strict=True)]
        mx = xs(pct(means[k]))
        frame = el("path", d=dot_path(rpts, r), cls="f-cand s-plate", stroke_width=1)
        frame += line(mx, y2c - 24, mx, y2c + 24, "s-ink", 3)
        if is_slow:
            counts: dict[int, int] = {}
            for i in idx:
                counts[i] = counts.get(i, 0) + 1
            picks = "".join(
                circle(x, y, r + 1 + 3.5 * j, "s-ink", fill="none", stroke_width=1.6)
                for i, (x, y) in enumerate(pos)
                for j in range(1, counts.get(i, 0) + 1)
            )
            unused = el(
                "path",
                d=dot_path([p for i, p in enumerate(pos) if i not in counts], r + 1),
                cls="f-plate",
                fill_opacity=0.75,
            )
            pl.add(pl.at(picks + unused, t0, t0 + dur))
            pl.add(pl.at(frame, t0 + 0.35, t0 + dur))
            sx, sy = slots[k]
            pl.add(
                el(
                    "circle",
                    cx=sx,
                    cy=sy,
                    r=r,
                    cls=f"f-cand s-plate {pl.clock.drop(t0 + 0.8, t0 + 1.35, y2c - sy)}",
                    stroke_width=1,
                )
            )
        else:
            pl.add(pl.at(frame, t0, t0 + dur))
            sx, sy = slots[k]
            pl.add(pl.at(circle(sx, sy, r, "f-cand s-plate", stroke_width=1), t0, keep=True))
    counter(pl, 780, 184, slow, slow_step)
    pl.add(
        pl.at(
            text(780, 184, f"{fast} more, fast", "mono f-muted", FS, "end"),
            slow * slow_step,
            t_end,
        )
    )
    # trim the tails: 5 % each side, then carry the interval up onto the data
    order = sorted(range(len(means)), key=lambda i: means[i])
    tails = order[:5] + order[-5:]
    pl.add(
        pl.at(
            el(
                "path",
                d=dot_path([slots[i] for i in tails], r + 1),
                cls="f-plate",
                fill_opacity=0.8,
            ),
            t_end,
            keep=True,
        ),
        pl.at(
            line(
                xs(pct(c_lo)),
                y3b + 8,
                xs(pct(c_hi)),
                y3b + 8,
                "s-better",
                4,
                stroke_linecap="round",
            )
            + text(xs(pct(c_hi)) + 10, y3b + 13, "90 %", "f-tbetter b"),
            t_end,
            keep=True,
        ),
        pl.at(
            line(
                xs(pct(c_lo)),
                y1c + 32,
                xs(pct(c_hi)),
                y1c + 32,
                "s-better",
                5,
                stroke_linecap="round",
            )
            + line(xs(pct(EST)), y1c + 24, xs(pct(EST)), y1c + 40, "s-better", 3)
            + text(
                xs(pct(c_hi)) + 10,
                y1c + 38,
                f"90 % CI {fmt(pct(c_lo))}, {fmt(pct(c_hi))} %",
                "f-tbetter b",
            ),
            t_end + 1.2,
            keep=True,
        ),
    )
    return pl


# ---------------------------------------------------------------- plate 6: forest and sweep


def plate_h6() -> Plate:
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
    xr = XorShift(47)  # the same generator and seed as the G2 forest of #1188
    hr = random.Random(61)
    rows = [("planning_time", "min", EST, C90, BOOTS[N_HOPS : 2 * N_HOPS])]
    for name, d, e, (a0, a1) in spec:
        s = (a1 - a0) / 2 / T90[19] * math.sqrt(20)
        base = [math.exp(0.08 * xr.norm()) for _ in range(20)]
        cand = [b * math.exp(e + s * xr.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], T90[19])
        se = (hi_ci - lo_ci) / 2 / T90[19]
        rows.append((name, d, m, (lo_ci, hi_ci), t_draws(hr, m, se, 19, N_HOPS)))
    rows.sort(key=lambda r: r[2])
    kinds = [
        verdict(a0, a1, MARGIN) if d == "max" else verdict(-a1, -a0, MARGIN)
        for _, d, _, (a0, a1), _ in rows
    ]
    n_imp = kinds.count("improved")
    n_un = kinds.count("unsure") + kinds.count("regressed")
    n_eq = kinds.count("equiv") + kinds.count("small")
    desc = (
        f"12 metrics, 20 paired runs each. Left: one plausible change per metric per frame. "
        f"Right: 90 % CIs. {n_imp} improved, {n_un} inconclusive, {n_eq} no change."
    )
    pl = Plate(f"{n_imp} better, {n_un} unclear, {n_eq} same", 492, desc, N_HOPS * HOP_STEP)
    vlo, vhi = -22.0, 14.0
    y0, step = 100, 26.0
    ybot = y0 + (len(rows) - 1) * step
    panels = ((200, 470, "one draw per frame"), (500, 750, "90 % CI"))
    for ax0, ax1, cap in panels:

        def xs(v: float, ax0: float = ax0, ax1: float = ax1) -> float:
            return ax0 + (v - vlo) / (vhi - vlo) * (ax1 - ax0)

        pl.add(
            rect(
                xs(-5), y0 - 14, xs(5) - xs(-5), ybot - y0 + 28, "f-band s-bandEdge", stroke_width=1
            ),
            line(xs(0), y0 - 14, xs(0), ybot + 14, "s-ink2", 1),
            text(ax0, 76, cap, "f-ink2"),
            text((ax0 + ax1) / 2, ybot + 62, "change (%)", "f-ink2", FS, "middle"),
        )
        for t in (-20, -10, 0, 10):
            pl.add(text(xs(t), ybot + 38, f"{t:+d}" if t else "0", "mono f-muted", FS, "middle"))
    hx0, hx1 = panels[0][0], panels[0][1]
    sx0, sx1 = panels[1][0], panels[1][1]

    def hx(v: float) -> float:
        return hx0 + (v - vlo) / (vhi - vlo) * (hx1 - hx0)

    def sx(v: float) -> float:
        return sx0 + (v - vlo) / (vhi - vlo) * (sx1 - sx0)

    for i, ((name, _d, m, (a0, a1), _), kind) in enumerate(zip(rows, kinds, strict=True)):
        y = y0 + i * step
        mark = VERDICT[kind][0]
        g, _ = glyph(kind, sx1 + 10, y + 6, FS + 2)
        pl.add(
            line(hx0, y, sx1, y, "s-grid"),
            text(20, y + 5, name, "f-ink2"),
            line(sx(pct(a0)), y, sx(pct(a1)), y, f"s-{mark}", 3, stroke_linecap="round"),
            circle(sx(pct(m)), y, 4.5, f"f-{mark} s-plate", stroke_width=1),
            g,
        )
    for k in range(N_HOPS):
        body = "".join(
            circle(
                hx(pct(r[4][k])),
                y0 + i * step,
                6,
                f"f-{cat(r[4][k], r[1] == 'min')} s-plate",
                stroke_width=1.2,
            )
            for i, r in enumerate(rows)
        )
        pl.add(pl.at(body, k * HOP_STEP, (k + 1) * HOP_STEP))
    pl.add(
        el(
            "g",
            "".join(
                circle(hx(pct(r[2])), y0 + i * step, 6, "f-ink2 s-plate")
                for i, r in enumerate(rows)
            ),
            cls="rmonly",
        )
    )
    counter(pl, hx1, ybot + 86, N_HOPS, HOP_STEP)
    return pl


def plate_h7() -> Plate:
    sp = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    xr = XorShift(59)  # the same generator and seed as the G6 sweep of #1188
    hr = random.Random(67)
    groups = []
    for v in sp:
        eff = 0.0 if v < 0.6 else -0.06 - 0.08 * (v - 0.6)
        b0 = 0.9 + 1.1 * v
        base = [b0 * math.exp(0.035 * xr.norm()) for _ in range(6)]
        cand = [b * math.exp(eff + 0.03 * xr.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], T90[5])
        se = (hi_ci - lo_ci) / 2 / T90[5]
        groups.append(
            (v, m, lo_ci, hi_ci, verdict(-hi_ci, -lo_ci, MARGIN), t_draws(hr, m, se, 5, N_HOPS))
        )
    last = groups[-1]
    desc = (
        "task_duration change over 8 speeds, 6 paired repeats each. Left: each frame is one "
        "plausible effect curve. Right: 90 % t intervals. "
        + "; ".join(f"{g[0]} m/s {fmt(pct(g[1]))} %" for g in groups)
    )
    pl = Plate(
        "Faster above 0.6 m/s", 450, desc, N_HOPS * HOP_STEP, (last[4], f"{fmt(pct(last[1]))} %")
    )
    vlo, vhi, y0, y1 = -24.0, 9.0, 90.0, 360.0

    def ys(v: float) -> float:
        return y1 - (v - vlo) / (vhi - vlo) * (y1 - y0)

    panels = ((80, 410, "one plausible curve per frame"), (470, 780, "90 % CI"))
    for ax0, ax1, cap in panels:

        def xs(v: float, ax0: float = ax0, ax1: float = ax1) -> float:
            return ax0 + 12 + (v - 0.2) / 1.4 * (ax1 - ax0 - 24)

        pl.add(
            rect(ax0, ys(5), ax1 - ax0, ys(-5) - ys(5), "f-band s-bandEdge", stroke_width=1),
            line(ax0, ys(0), ax1, ys(0), "s-ink2", 1),
            text(ax0, 76, cap, "f-ink2"),
            text((ax0 + ax1) / 2, y1 + 50, "speed (m/s)", "f-ink2", FS, "middle"),
        )
        for t in (-20, -10):
            pl.add(line(ax0, ys(t), ax1, ys(t), "s-grid"))
        for t in (-20, -10, 0):
            pl.add(text(ax0 - 6, ys(t) + 5, f"{t:+d} %" if t else "0", "mono f-muted", FS, "end"))
        for v in sp[::2]:
            pl.add(text(xs(v), y1 + 24, f"{v:.1f}", "mono f-muted", FS, "middle"))
    hxs = [panels[0][0] + 12 + (v - 0.2) / 1.4 * (panels[0][1] - panels[0][0] - 24) for v in sp]
    sxs = [panels[1][0] + 12 + (v - 0.2) / 1.4 * (panels[1][1] - panels[1][0] - 24) for v in sp]
    for x, (_, m, a, b, kind, _) in zip(sxs, groups, strict=True):
        mark = VERDICT[kind][0]
        pl.add(
            line(x, ys(pct(a)), x, ys(pct(b)), f"s-{mark}", 3, stroke_linecap="round"),
            circle(x, ys(pct(m)), 5, f"f-{mark} s-plate", stroke_width=1),
        )
    for k in range(N_HOPS):
        pts = [(x, ys(pct(g[5][k]))) for x, g in zip(hxs, groups, strict=True)]
        body = el(
            "path",
            d="M" + "L".join(f"{num(x)} {num(y)}" for x, y in pts),
            cls="s-cand",
            fill="none",
            stroke_width=2.5,
        )
        body += "".join(
            circle(x, y, 5.5, f"f-{cat(g[5][k])} s-plate", stroke_width=1.2)
            for (x, y), g in zip(pts, groups, strict=True)
        )
        pl.add(pl.at(body, k * HOP_STEP, (k + 1) * HOP_STEP))
    pl.add(
        el(
            "g",
            el(
                "path",
                d="M"
                + "L".join(
                    f"{num(x)} {num(ys(pct(g[1])))}" for x, g in zip(hxs, groups, strict=True)
                ),
                cls="s-cand",
                fill="none",
                stroke_width=2.5,
            ),
            cls="rmonly",
        )
    )
    counter(pl, panels[0][1], y1 + 76, N_HOPS, HOP_STEP)
    return pl


PLATES = {
    "h1_hops_shift.svg": plate_h1,
    "h2_hops_inconclusive.svg": plate_h2,
    "h3_hops_rates.svg": plate_h3,
    "h4_dance_of_cis.svg": plate_h4,
    "h5_bootstrap_buildup.svg": plate_h5,
    "h6_hops_forest.svg": plate_h6,
    "h7_hops_sweep.svg": plate_h7,
}


def main() -> None:
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
