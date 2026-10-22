"""Write the dash-flow demo plates as standalone SVG files.

The data are synthetic and seeded, so every run writes the same files. The script uses
only the standard library:

    python docs/evidence_dash_flow/make_svgs.py           # write the plates
    python docs/evidence_dash_flow/make_svgs.py --check   # check the motion rule

The style is the one of #1188: every sample is a dot, the margin is a band on the
metric's own axis, the CI is a capped interval, and text is a short finding, one effect
number with its verdict glyph, and axis labels.

The motion rule: dots, bars, medians, bands, intervals, text and glyphs never move,
resize, fade or glow. The only motion is dashes that flow along secondary lines, made
with stroke-dashoffset on a dashed stroke. Every frame is the complete still chart, and
``prefers-reduced-motion`` stops all flow. ``--check`` parses every SVG's CSS and fails
if anything else animates.
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
# C: the stroke opacity of the flowing pair lines
CONTRASTS = {"C1": 0.35, "C2": 0.6, "C3": 0.9}
DEFAULT = Look("S2P2C2", 8.0, 4.0, 4.0, 0.6)
EDGE = Look("edge", 4.0, 1.0, 3.0, 0.9)  # the ±Δ band edges: fine dots, slow

BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
.dash{{stroke-dasharray:4 4}}
"""
REDUCED = "\n@media (prefers-reduced-motion:reduce){.fl{animation:none!important}}\n"


def size_look(look: Look, size: float, typical: float) -> Look:
    """Return look with its speed scaled by size / typical (the E1 variant)."""
    speed = look.speed * min(max(size / typical, 0.4), 2.5)
    speed = round(speed * 2) / 2
    return look._replace(code=f"E{speed}", speed=speed)


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


# ---------------------------------------------------------------- shared marks


MOVED = {"improved", "regressed"}


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
    est: float,
    kind: str,
    lower_better: bool = True,
    ticks: list[float] | None = None,
    tick_fmt=None,
    tick_labels: bool = True,
    labels: str = "two",
    r: float = 4.5,
    boots: list[float] | None = None,
    mark_glyph: bool = False,
    flows: tuple[str, ...] = (),
    look: Look = DEFAULT,
    size_speed: bool = False,
) -> str:
    """Draw base and candidate as beeswarm dot columns on the metric's own axis.

    The ±Δ band sits around the base median. The bracket beside the candidate column is
    the CI of the shift, drawn where it puts the candidate median (base median x shift).
    flows names the secondary lines that flow: "pairs" (base run to its candidate run),
    "connector" (base median to candidate median), "ref" (the base median carried across
    the candidate column) and "edges" (the band edges). Lines flow only for a change.
    """
    out = []

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    px = x0 + (48 if tick_labels else 0)
    wid = x1 - px
    cb, cc = px + wid * 0.27, px + wid * 0.6
    for t in ticks or []:
        out.append(line(px, ys(t), x1, ys(t), "s-grid"))
        if tick_labels and tick_fmt:
            out.append(text(px - 7, ys(t) + 5, tick_fmt(t), "mono f-muted", FS, "end"))
    bmed, cmed = quant(base, 0.5), quant(cand, 0.5)
    top, bot = ys(bmed * math.exp(MARGIN)), ys(bmed * math.exp(-MARGIN))
    moved = kind in MOVED
    if "edges" in flows:
        out.append(rect(px + 2, top, x1 - px - 4, bot - top, "f-band"))
        mid = (px + x1) / 2
        cls = pl.flow(EDGE)
        for yy in (top, bot):  # each edge flows from both ends toward the middle
            out += [
                line(px + 2, yy, mid, yy, f"s-ink2 {cls}", 1.6, stroke_opacity=EDGE.opacity),
                line(x1 - 2, yy, mid, yy, f"s-ink2 {cls}", 1.6, stroke_opacity=EDGE.opacity),
            ]
    else:
        out.append(rect(px + 2, top, x1 - px - 4, bot - top, "f-band s-bandEdge", stroke_width=1))
    pb, pc = [ys(v) for v in base], [ys(v) for v in cand]
    ob, oc = swarm(pb, r), swarm(pc, r)
    mark, _, _ = VERDICT[kind]
    typical = mean([abs(math.log(c / b)) for b, c in zip(base, cand, strict=True)])
    for i in range(len(base)):
        better = (cand[i] < base[i]) == lower_better
        tok = "cand" if better else "worse"
        xa, xb = cb + ob[i], cc + oc[i]
        out.append(
            line(xa, pb[i], xb, pc[i], f"s-{tok}", 1.2, stroke_opacity=0.3 if better else 0.6)
        )
        if "pairs" in flows and moved:  # dashes flow from the base run to its candidate run
            lk = size_look(look, abs(math.log(cand[i] / base[i])), typical) if size_speed else look
            out.append(
                line(xa, pb[i], xb, pc[i], f"s-{tok} {pl.flow(lk)}", 1.6, stroke_opacity=lk.opacity)
            )
    hws = [min(max(abs(o) for o in offs) + r + 5, wid * 0.15) for offs in (ob, oc)]
    bx = min(cc + max(abs(o) for o in oc) + r + 14, x1 - 8)
    if "ref" in flows:  # the base median, carried across the candidate column
        cls = pl.flow(look) if moved else "dash"
        out.append(line(cb + hws[0], ys(bmed), bx - 12, ys(bmed), f"s-ink2 {cls}", 1.8))
    out += [
        circle(cb + o, p, r, "f-base s-plate", stroke_width=1) for o, p in zip(ob, pb, strict=True)
    ]
    out += [
        circle(cc + o, p, r, "f-cand s-plate", stroke_width=1) for o, p in zip(oc, pc, strict=True)
    ]
    if "connector" in flows:
        cls = pl.flow(look) if moved else "dash"
        out.append(
            line(
                cb + hws[0] + 4,
                ys(bmed),
                cc - hws[1] - 4,
                ys(cmed),
                f"s-{mark} {cls}",
                2.5,
                stroke_opacity=1 if moved else 0.6,
            )
        )
    for (cx, med, tok), hw in zip(((cb, bmed, "base"), (cc, cmed, "cand")), hws, strict=True):
        bar = line(cx - hw, ys(med), cx + hw, ys(med), "s-plate", 9, stroke_linecap="round")
        bar += line(cx - hw, ys(med), cx + hw, ys(med), f"s-{tok}", 5, stroke_linecap="round")
        out.append(bar)
    y_lo, y_hi = sorted((ys(bmed * math.exp(ci[0])), ys(bmed * math.exp(ci[1]))))
    out.append(
        el(
            "path",
            d=f"M{num(bx - 7)} {num(y_lo)}H{num(bx)}V{num(y_hi)}H{num(bx - 7)}",
            cls=f"s-{mark}",
            fill="none",
            stroke_width=3,
            stroke_linecap="round",
            stroke_linejoin="round",
        )
    )
    ye = ys(bmed * math.exp(est))
    out.append(line(bx - 9, ye, bx + 3, ye, f"s-{mark}", 3, stroke_linecap="round"))
    if boots:
        step = 2.5
        hist: dict[int, int] = {}
        for b in boots:
            k = round(ys(bmed * math.exp(b)) / step)
            hist[k] = hist.get(k, 0) + 1
        hm = max(hist.values())
        ks = range(min(hist) - 1, max(hist) + 2)
        d = f"M{num(bx + 8)} {num(ks[0] * step)}"
        d += "".join(f"L{num(bx + 8 + hist.get(k, 0) / hm * 44)} {num(k * step)}" for k in ks)
        d += f"L{num(bx + 8)} {num(ks[-1] * step)}Z"
        out.append(el("path", d=d, cls=f"f-{mark} s-{mark}", fill_opacity=0.22, stroke_width=1))
    if mark_glyph:
        g, _ = glyph(kind, bx - 9, y_lo - 9, FS + 1)
        out.append(g)
    if labels == "two":
        for cx, name, n in ((cb, "base", len(base)), (cc, "candidate", len(cand))):
            out += [
                text(cx, y1 + 26, name, "f-ink2", FS, "middle"),
                text(cx, y1 + 45, f"n={n}", "mono f-muted", FS, "middle"),
            ]
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


def plan_kind() -> str:
    return verdict(-C90[1], -C90[0], MARGIN)


def plan_title() -> str:
    return f"Planning is {abs(pct(EST)):.0f} % faster"


# ---------------------------------------------------------------- section 1: where flow goes


def plate_est(code: str, flows: tuple[str, ...], look: Look = DEFAULT) -> Plate:
    """Draw planning_time as two dot columns, with flows on the named secondary lines."""
    kind = plan_kind()
    desc = (
        f"planning_time, 20 ABBA pairs on 4 VMs: {sum(p.cand < p.base for p in PAIRS)} of 20 "
        f"pairs faster. Effect {fmt(pct(EST))} %, 90 % CI [{fmt(pct(C90[0]))}, "
        f"{fmt(pct(C90[1]))}] %."
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
            est=EST,
            kind=kind,
            ticks=nice_ticks(lo, hi, 5),
            tick_fmt=lambda t: f"{t:.1f} s",
            labels="one",
            r=5.5,
            boots=BOOTS,
            flows=flows,
            look=look,
        ),
        run_rows(Strip(540, 120, cell=14, pair_gap=5, pitch=24, label_w=54), abba_rows(PAIRS)),
        text(594, 236, "run order →", "f-muted"),
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
        a0, a1 = self.ci
        return verdict(a0, a1, MARGIN) if self.direction == "max" else verdict(-a1, -a0, MARGIN)


def forest_metrics() -> list[Metric]:
    """Return #1188's 12 metrics, sorted by effect. The draws match its G2 stream."""
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
    rows = [
        Metric("planning_time", "min", LOG_DIFF, EST, C90),
        Metric("tracking_error_rms", "min", TRACK_LD, TRACK_EST, TRACK_C90),
    ]
    for name, d, e, (a0, a1) in spec:
        s = (a1 - a0) / 2 / 1.729 * math.sqrt(20)
        base = [math.exp(0.08 * rng.norm()) for _ in range(20)]
        cand = [b * math.exp(e + s * rng.norm()) for b in base]
        diffs = [math.log(c / b) for b, c in zip(base, cand, strict=True)]
        m, lo_ci, hi_ci = t_ci(diffs, 1.729)
        if name == "tracking_error_rms":
            continue  # drawn from TRACK, as in G1; the draws keep the other rows' streams
        rows.append(Metric(name, d, diffs, m, (lo_ci, hi_ci)))
    rows.sort(key=lambda r: r.est)
    return rows


def forest_title(rows: list[Metric]) -> str:
    kinds = [r.kind for r in rows]
    n_imp = kinds.count("improved")
    n_un = kinds.count("unsure") + kinds.count("regressed")
    n_eq = kinds.count("equiv") + kinds.count("small")
    return f"{n_imp} better, {n_un} unclear, {n_eq} same"


def plate_forest(code: str, look: Look = DEFAULT) -> Plate:
    rows = forest_metrics()
    desc = "12 metrics, change vs base with 90 % CI, ±5 % band: " + "; ".join(
        f"{r.name} {fmt(pct(r.est))} %" for r in rows
    )
    pitch, top = 38, 92
    bottom = top + pitch * (len(rows) - 1)
    pl = Plate(forest_title(rows), bottom + 96, desc, code=code)
    lo, hi = axis_range([d for r in rows for d in r.diffs], 0.04)
    ax0, ax1 = 220, 722

    def xs(v: float) -> float:
        return ax0 + (v - lo) / (hi - lo) * (ax1 - ax0)

    pl.add(rect(xs(-MARGIN), top - 24, xs(MARGIN) - xs(-MARGIN), bottom - top + 48, "f-band"))
    for t in nice_ticks(pct(lo), pct(hi), 5):
        x = xs(math.log(1 + t / 100))
        pl.add(
            line(
                x, top - 24, x, bottom + 24, "s-muted" if t == 0 else "s-grid", 1.5 if t == 0 else 1
            ),
            text(x, bottom + 46, "0" if t == 0 else f"{fmt(t, 0)} %", "mono f-muted", FS, "middle"),
        )
    for i, r in enumerate(rows):
        y = top + i * pitch
        kind = r.kind
        mark, _, _ = VERDICT[kind]
        pl.add(text(20, y + 5, r.name, "mono f-ink2"))
        dx = [xs(d) for d in r.diffs]
        pl.add(
            *(
                circle(x, y + 7 + o * 0.5, 2.2, "f-cand", fill_opacity=0.5)
                for x, o in zip(dx, swarm(dx, 2.2, one_sided=True), strict=True)
            )
        )
        yc = y - 6
        if kind in MOVED:  # flows from 0 toward the estimate
            pl.add(line(xs(0), yc, xs(r.est), yc, f"s-{mark} {pl.flow(look)}", 2.2))
        pl.add(
            el(
                "path",
                d=f"M{num(xs(r.ci[0]))} {num(yc - 5)}v10M{num(xs(r.ci[0]))} {num(yc)}"
                f"H{num(xs(r.ci[1]))}M{num(xs(r.ci[1]))} {num(yc - 5)}v10",
                cls=f"s-{mark}",
                fill="none",
                stroke_width=2.5,
                stroke_linecap="round",
            ),
            circle(xs(r.est), yc, 4.5, f"f-{mark} s-plate", stroke_width=1.5),
        )
        g, _ = glyph(kind, ax1 + 22, y + 5, FS + 3)
        pl.add(g)
    pl.add(
        text((ax0 + ax1) / 2, bottom + 70, "change vs base", "f-ink2", FS, "middle"),
        legend(W - 20, 66, [("f-cand", "one pair"), ("f-band", "±5 %")]),
    )
    return pl


def plate_sweep(code: str, look: Look = DEFAULT) -> Plate:
    sp = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    rng = XorShift(59)
    groups = []
    for v in sp:
        eff = 0.0 if v < 0.6 else -0.06 - 0.08 * (v - 0.6)
        b0 = 0.9 + 1.1 * v
        base = [b0 * math.exp(0.035 * rng.norm()) for _ in range(6)]
        cand = [b * math.exp(eff + 0.03 * rng.norm()) for b in base]
        m, lo_ci, hi_ci = t_ci([math.log(c / b) for b, c in zip(base, cand, strict=True)], 2.015)
        groups.append((v, base, cand, m, (lo_ci, hi_ci), verdict(-hi_ci, -lo_ci, MARGIN)))
    last = groups[-1]
    desc = "task_duration, 8 speeds x 6 paired repeats: " + "; ".join(
        f"{g[0]} m/s {fmt(pct(g[3]))} %" for g in groups
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
    for k, (v, base, cand, m, ci, kind) in enumerate(groups):
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
                est=m,
                kind=kind,
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
    for mx, yb, yc, kind in mids:  # the gap at each speed, base median to candidate median
        if kind in MOVED:
            mark = VERDICT[kind][0]
            pl.add(line(mx, yb, mx, yc, f"s-{mark} {pl.flow(look)}", 2))
        else:
            pl.add(line(mx, yb, mx, yc, "s-muted dash", 1.5, stroke_opacity=0.6))
    pl.add(
        text((x0 + x1) / 2, y1 + 54, "speed (m/s)", "f-ink2", FS, "middle"),
        legend(W - 20, y1 + 54, ARMS),
    )
    return pl


def _waffle(
    pl: Plate,
    look: Look,
    x0: float,
    y0: float,
    spec: tuple[int, int, str, int, float],
    changed: set[int],
) -> None:
    """Draw n runs as squares, a cross for each failure.

    Runs that differ from their base runs get a dashed outline that flows around them.
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
    # one outline around each row run of changed squares, so neighbours do not collide
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
                f"s-better {pl.flow(look)}",
                rx=5,
                fill="none",
                stroke_width=2,
            )
        )


def plate_waffle(code: str, look: Look = DEFAULT) -> Plate:
    desc = (
        f"task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}: {TS_TXT}, 90 % CI {TS_CI_TXT}, "
        f"inconclusive. required_sigkill: base {SK_BASE}/{SK_N} killed, candidate "
        f"{SK_CAND}/{SK_N}, true rate at most {SK_BOUND * 100:.1f} %: improved."
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
    _waffle(pl, look, 110, 146, (TS_N, TS_N - TS_BASE, "base", 9, 18), set())
    flipped = set(range(TS_BASE, TS_CAND))  # failed on base, passed on the candidate
    _waffle(pl, look, 110, 196, (TS_N, TS_N - TS_CAND, "cand", 9, 18), flipped)
    pl.add(
        text(330, 165, f"{TS_BASE}/{TS_N}", "mono f-muted"),
        text(330, 215, f"{TS_CAND}/{TS_N}", "mono f-muted"),
    )

    def sc(v: float) -> float:
        return 110 + (v + 0.3) / 0.6 * 220

    pl.add(
        text(20, 277, "change"), rect(sc(-0.05), 258, sc(0.05) - sc(-0.05), 26, "f-band s-bandEdge")
    )
    for v in (-0.2, 0, 0.2):
        lab = "0" if v == 0 else f"{fmt(v * 100, 0)} pp"
        pl.add(
            line(sc(v), 254, sc(v), 288, "s-muted" if v == 0 else "s-grid"),
            text(sc(v), 310, lab, "mono f-muted", FS, "middle"),
        )
    pl.add(
        line(sc(TS_CI[0]), 271, sc(TS_CI[1]), 271, "s-unsure", 5, stroke_linecap="round"),
        circle(sc(TS_DIFF), 271, 6, "f-plate s-unsure", stroke_width=2.5),
    )
    fx = 420
    g, _ = glyph("improved", fx + 226, 120, 26)
    pl.add(
        text(fx, 82, "required_sigkill", "mono f-ink2"),
        text(fx, 120, f"{SK_BASE / SK_N * 100:.0f} % → ≤ {SK_BOUND * 100:.1f} %", "f-ink bb", 28),
        g,
        text(fx, 165, "base"),
        text(fx, 215, "candidate"),
    )
    _waffle(pl, look, fx + 90, 150, (SK_N, SK_BASE, "base", 15, 14), set())
    killed = set(range(SK_N - SK_BASE, SK_N))  # killed on base, clean on the candidate
    _waffle(pl, look, fx + 90, 200, (SK_N, SK_CAND, "cand", 15, 14), killed)
    rx0, rx1 = fx + 90, 770

    def rs(v: float) -> float:
        return rx0 + v / 300 * (rx1 - rx0)

    pl.add(
        text(fx, 277, "runs"),
        rect(rx0, 266, rx1 - rx0, 10, "f-chip", rx=5),
        rect(rx0, 266, rs(SK_N) - rx0, 10, "f-cand", rx=5),
    )
    for b, v in SK_RUNS.items():
        bound = f"≤{b * 100:.0f} %"
        anchor = "middle" if v < 200 else "end"
        pl.add(
            line(rs(v), 258, rs(v), 284, "s-ink2", 1.5),
            text(rs(v), 252, bound, "mono f-muted", FS, anchor),
            text(rs(v), 306, str(v), "mono f-muted", FS, anchor),
        )
    return pl


def plate_design(code: str, look: Look = DEFAULT) -> Plate:
    desc = (
        "This run: paired ABBA on 4 VMs, 5 pairs each, each pair back to back on one VM; "
        "each pair's base run flows to its candidate run. Blocked contrast: all base then "
        "all candidate on one VM, so drift lands on the one boundary between the blocks."
    )
    pl = Plate("Paired ABBA on 4 VMs", 290, desc, code=code)
    pl.legend = True
    st = Strip(20, 80, cell=22, h=16, gap=4, pair_gap=10, pitch=28, label_w=90)
    rows = abba_rows(PAIRS)
    pl.add(run_rows(st, rows))
    for r, (_, seq) in enumerate(rows):  # an arc under each pair, from base run to candidate
        yb = st.y(r) + st.h + 2
        for j in range(0, len(seq), 2):
            ia = j + seq[j : j + 2].index("A")
            ib = j + seq[j : j + 2].index("B")
            xa, xb = st.x(ia) + st.cell / 2, st.x(ib) + st.cell / 2
            d = f"M{num(xa)} {num(yb)}Q{num((xa + xb) / 2)} {num(yb + 11)} {num(xb)} {num(yb)}"
            pl.add(el("path", d=d, cls=f"s-cand {pl.flow(look)}", fill="none", stroke_width=1.8))
    blk = Strip(20, 210, cell=22, h=16, gap=4, label_w=90, pairs=False)
    edge = blk.x(10) - blk.gap / 2
    pl.add(
        run_rows(blk, [("blocked", "A" * 10 + "B" * 10)]),
        line(edge, 196, edge, 240, f"s-unsure {pl.flow(look)}", 2.5),
        text(blk.x(19) + blk.cell + 14, 223, "drift lands here", "f-muted"),
        line(110, 258, 600, 258, "s-muted"),
        el("path", d="M600 253L609 258L600 263Z", cls="f-muted"),
        text(618, 263, "run order", "f-muted"),
    )
    return pl


# F10: a synthetic history of 30 commits. The last one is this PR, with the paired effect.
_HR = XorShift(1010)
HIST: list[list[float]] = []
_level = quant([p.base for p in PAIRS], 0.5)
for _k in range(30):
    _level *= math.exp(EST) if _k == 29 else math.exp(0.006 * _HR.norm())
    HIST.append([_level * math.exp(0.05 * _HR.norm()) for _ in range(6)])
HIST_MED = [quant(h, 0.5) for h in HIST]
HIST_STEP = math.log(HIST_MED[-1] / HIST_MED[-2])


def plate_history(code: str, look: Look = DEFAULT) -> Plate:
    kind = "improved" if HIST_STEP < -MARGIN else "unsure"
    desc = (
        "Synthetic history: planning_time on 30 commits, 6 runs each; the last commit is this "
        f"PR. Its median steps {fmt(pct(HIST_STEP))} % from the commit before."
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
    top, bot = ys(ref * math.exp(MARGIN)), ys(ref * math.exp(-MARGIN))
    pl.add(rect(x0, top, x1 - x0, bot - top, "f-band s-bandEdge", stroke_width=1))
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
    pr = f"M{num(xe)} {num(ys(HIST_MED[-2]))}V{num(ys(HIST_MED[-1]))}H{num(xe + step)}"  # the PR step: the only line that flows
    pl.add(el("path", d=pr, cls=f"s-better {pl.flow(look)}", fill="none", stroke_width=2.5))
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


# ---------------------------------------------------------------- section 2: how flow looks


def look_variants() -> list[list[tuple[str, Look, bool]]]:
    """Return the grid rows: speed (with the size-speed variant), pattern, contrast."""
    _, s2 = SPEEDS["S2"]
    _, d2, g2 = PATTERNS["P2"]
    c2 = CONTRASTS["C2"]
    speed = [(f"{k} {w}", Look(k, v, d2, g2, c2), False) for k, (w, v) in SPEEDS.items()]
    speed.append(("E1 size → speed", Look("E1", s2, d2, g2, c2), True))
    pattern = [(f"{k} {w}", Look(k, s2, d, g, c2), False) for k, (w, d, g) in PATTERNS.items()]
    contrast = [(f"{k} {c:g}", Look(k, s2, d2, g2, c), False) for k, c in CONTRASTS.items()]
    return [speed, pattern, contrast]


def plate_looks(code: str) -> Plate:
    desc = (
        "The F3 chart (pair lines and median connector flow) in ten looks. Speed S1-S3 is "
        "4, 8 and 16 px/s; E1 scales each pair line's speed by its change. Pattern P1-P3 is "
        "1-3, 4-4 and 8-6 px. Contrast C1-C3 is the pair lines' stroke opacity."
    )
    pl = Plate("Pick a speed, pattern, contrast", 676, desc, code=code)
    kind = plan_kind()
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    for r, row in enumerate(look_variants()):
        for k, (label, look, by_size) in enumerate(row):
            x0, y = 20 + k * 192, 62 + r * 204
            pl.add(
                text(x0 + 4, y + 18, label, "mono f-ink2 b"),
                dot_panel(
                    pl,
                    x0=x0,
                    x1=x0 + 180,
                    y0=y + 32,
                    y1=y + 190,
                    base=[p.base for p in PAIRS],
                    cand=[p.cand for p in PAIRS],
                    lo=lo,
                    hi=hi,
                    ci=C90,
                    est=EST,
                    kind=kind,
                    tick_labels=False,
                    labels="none",
                    r=2.8,
                    flows=("pairs", "connector"),
                    look=look,
                    size_speed=by_size,
                ),
            )
    return pl


# ---------------------------------------------------------------- section 3: the report set


def _binary_panel(pl: Plate, look: Look, x0: float, x1: float, y0: float, y1: float) -> str:
    """Draw task_success as one square per run, a cross for each failure."""
    out = []
    size, gap = 18, 5
    px = x0 + 48
    wid = x1 - px
    for cx, n_fail, tok, name, count in (
        (px + wid * 0.27, TS_N - TS_BASE, "base", "base", f"{TS_BASE}/{TS_N}"),
        (px + wid * 0.6, TS_N - TS_CAND, "cand", "candidate", f"{TS_CAND}/{TS_N}"),
    ):
        left = cx - (3 * size + 2 * gap) / 2
        for i in range(TS_N):
            r, k = divmod(i, 3)
            x, y = left + k * (size + gap), y0 + 40 + r * (size + gap)
            if i >= TS_N - n_fail:
                cross = f"M{num(x + 4.5)} {num(y + 4.5)}l9 9m0 -9l-9 9"
                out += [
                    rect(x, y, size, size, "f-plate s-worse", rx=3, stroke_width=2),
                    el("path", d=cross, cls="s-worse", stroke_width=2),
                ]
                continue
            out.append(rect(x, y, size, size, f"f-{tok}", rx=3))
            if tok == "cand" and TS_BASE <= i < TS_CAND:  # passed here, failed on base
                out.append(
                    rect(
                        x - 3.5,
                        y - 3.5,
                        size + 7,
                        size + 7,
                        f"s-better {pl.flow(look)}",
                        rx=5,
                        fill="none",
                        stroke_width=2,
                    )
                )
        out += [
            text(cx, y1 + 26, name, "f-ink2", FS, "middle"),
            text(cx, y1 + 45, count, "mono f-muted", FS, "middle"),
        ]
    return "".join(out)


def plate_scorecard(code: str, look: Look = DEFAULT) -> Plate:
    k_track = verdict(-TRACK_C90[1], -TRACK_C90[0], MARGIN)
    desc = (
        f"planning_time {fmt(pct(EST))} % (90 % CI {fmt(pct(C90[0]))} to {fmt(pct(C90[1]))}), "
        f"improved; task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}, {TS_TXT}, inconclusive; "
        f"tracking_error_rms {fmt(pct(TRACK_EST))} %, no change. Paired ABBA, 20 pairs on 4 VMs."
    )
    pl = Plate(plan_title(), 536, desc, code=code)
    panels = [
        ("planning_time · s", f"{fmt(pct(EST))} %", plan_kind(), PAIRS, C90, EST),
        ("task_success", TS_TXT, TS_KIND, None, None, None),
        ("tracking_error · mm", f"{fmt(pct(TRACK_EST))} %", k_track, TRACK, TRACK_C90, TRACK_EST),
    ]
    for i, (name, big, kind, pairs, ci, est) in enumerate(panels):
        x0 = 20 + i * 258
        x1 = x0 + 244
        g, _ = glyph(kind, x0 + len(big) * 15.5 + 8, 116, 26)
        pl.add(text(x0, 80, name, "mono f-ink2"), text(x0, 116, big, "f-ink bb", 28), g)
        y0, y1 = 140, 360
        if pairs is None or ci is None or est is None:
            pl.add(_binary_panel(pl, look, x0, x1, y0, y1))
            continue
        lo, hi = axis_range([p.base for p in pairs] + [p.cand for p in pairs])
        pl.add(
            dot_panel(
                pl,
                x0=x0,
                x1=x1,
                y0=y0,
                y1=y1,
                base=[p.base for p in pairs],
                cand=[p.cand for p in pairs],
                lo=lo,
                hi=hi,
                ci=ci,
                est=est,
                kind=kind,
                ticks=nice_ticks(lo, hi),
                tick_fmt=lambda t: f"{t:g}",
                r=4,
                flows=("pairs", "connector"),
                look=look,
            )
        )
    pl.add(
        run_rows(Strip(20, 430), abba_rows(PAIRS)),
        text(308, 442, "run order →", "f-muted"),
    )
    return pl


RECOMMENDED = DEFAULT

PLATES = {
    "f01_pairs.svg": lambda: plate_est("F1 · pair lines flow", ("pairs",)),
    "f02_connector.svg": lambda: plate_est("F2 · median connector flows", ("connector",)),
    "f03_pairs_connector.svg": lambda: plate_est(
        "F3 · pair lines + median connector flow", ("pairs", "connector")
    ),
    "f04_base_reference.svg": lambda: plate_est("F4 · base median carried across", ("ref",)),
    "f05_margin_edges.svg": lambda: plate_est("F5 · ±Δ band edges flow inward", ("edges",)),
    "f06_forest.svg": lambda: plate_forest("F6 · 0 → estimate flows on ▲▼ rows"),
    "f07_sweep.svg": lambda: plate_sweep("F7 · gap flows where beyond ±Δ"),
    "f08_waffle.svg": lambda: plate_waffle("F8 · outline flows on changed runs"),
    "f09_design.svg": lambda: plate_design("F9 · pairs flow; block edge flows"),
    "f10_history.svg": lambda: plate_history("F10 · only the PR step flows · synthetic"),
    "l1_looks.svg": lambda: plate_looks("S speed · P pattern · C contrast · E1 size → speed"),
    "r1_scorecard.svg": lambda: plate_scorecard("R1 · scorecard", RECOMMENDED),
    "r2_forest.svg": lambda: plate_forest("R2 · forest", RECOMMENDED),
    "r3_estimation.svg": lambda: plate_est("R3 · estimation", ("pairs", "connector"), RECOMMENDED),
    "r4_waffle.svg": lambda: plate_waffle("R4 · waffle", RECOMMENDED),
    "r5_design.svg": lambda: plate_design("R5 · design", RECOMMENDED),
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


def main() -> None:
    if "--check" in sys.argv:
        bad, total = 0, 0
        for path in sorted(OUT.glob("*.svg")):
            count, errs = check_motion(path)
            total += count
            size = path.stat().st_size
            if size >= 150_000:
                errs.append(f"{size} bytes, over 150 KB")
            bad += bool(errs)
            status = "ok" if not errs else "FAIL " + "; ".join(errs)
            sys.stdout.write(f"{path.name}: {count} animated dashed strokes, {size} B, {status}\n")
        sys.stdout.write(f"total {total} animated elements; {bad} files fail\n")
        sys.exit(1 if bad else 0)
    if "--facts" in sys.argv:
        rows = forest_metrics()
        sys.stdout.write(
            f"planning {fmt(pct(EST))} % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}]\n"
            f"forest {forest_title(rows)}: "
            + ", ".join(f"{r.name} {r.kind}" for r in rows)
            + f"\nhistory step {fmt(pct(HIST_STEP))} %\n"
        )
        return
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
