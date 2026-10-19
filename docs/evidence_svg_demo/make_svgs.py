"""Write the statistical-evidence demo plates as standalone SVG files.

The data are synthetic and seeded, so every run writes the same files. The script uses
only the standard library:

    python docs/evidence_svg_demo/make_svgs.py

The plates show, they do not tell: every sample is a dot, the margin is a band on the
metric's own axis, and the design is drawn (pair lines, run-order squares). Text is a
short finding, one effect number with its verdict glyph, and axis labels.

Each SVG carries a light and a dark palette (``prefers-color-scheme``). Motion is
limited to two things: dashes that flow in the direction of a change, and a highlight
that walks the run-order strip. No data mark moves, so every frame is the complete chart.
``prefers-reduced-motion`` turns it off.
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

# Motion: dashes flow in the direction of a change, and the run-order strip is walked.
# No data mark changes position.
BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
@keyframes drift{{to{{stroke-dashoffset:-24}}}}
@keyframes flow{{to{{stroke-dashoffset:-20}}}}
.shimmer{{stroke-dasharray:4 8;animation:drift 4s linear infinite}}
.flow{{stroke-dasharray:6 4;animation:flow 3s linear infinite}}
.still{{stroke-dasharray:6 4}}
@media (prefers-reduced-motion:reduce){{
.shimmer,.flow{{animation:none}}
.cur{{animation:none!important}}.shimmer,.overlay{{display:none}}}}
"""


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

# G8: power with n unpaired runs per arm, for an assumed run-to-run SD (log scale)
PW_N, PW_SD = 8, 0.07
PW_MDE = (Z90 + Z80) * PW_SD * math.sqrt(2 / PW_N)
PW_NEED = math.ceil(2 * ((Z90 + Z80) * PW_SD / MARGIN) ** 2)

# G9: run order. Drift is the OLS slope of log value on run index inside each arm, after
# each VM's own level is removed. The A/A band is an assumed noise floor, not measured.
AA_BAND = 0.03
RUNS: list[tuple[int, int, str, float]] = []  # (run index, VM, arm, value)
for _p in PAIRS:
    for _a in _p.order:
        RUNS.append((len(RUNS), _p.shard, _a, _p.base if _a == "A" else _p.cand))


def _slope(arm: str) -> tuple[float, float, float]:
    pts = []
    for vm in range(4):
        rs = [(i, math.log(v)) for i, s_, a, v in RUNS if s_ == vm and a == arm]
        m = mean([y for _, y in rs])
        pts += [(i, y - m) for i, y in rs]
    xm, ym = mean([x for x, _ in pts]), mean([y for _, y in pts])
    sxx = sum((x - xm) ** 2 for x, _ in pts)
    b = sum((x - xm) * (y - ym) for x, y in pts) / sxx
    res = [y - ym - b * (x - xm) for x, y in pts]
    se = math.sqrt(sum(r * r for r in res) / (len(pts) - 2 - 3) / sxx)  # 2 + 3 VM levels
    t = 1.753  # t(0.95, 15): 20 runs less the slope and 4 VM levels
    return b, b - t * se, b + t * se


DRIFT = {arm: _slope(arm) for arm in "AB"}
_vm_med = [quant([v for _, s_, a, v in RUNS if s_ == vm and a == "A"], 0.5) for vm in range(4)]
VM2_SLOW = _vm_med[1] / quant([_vm_med[0], _vm_med[2], _vm_med[3]], 0.5) - 1

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


class Cursor:
    """A playhead that walks the runs in the order they ran: pure CSS, no JS.

    Every highlight shares one loop of n steps plus a pause. Each one waits run_index x
    step, so together they read as one moving cursor. The highlights are hidden when
    there is no motion, so the still frame is the plain chart.
    """

    def __init__(self, n: int, step: float = 0.45, pause: float = 2.0, peak: float = 0.65) -> None:
        self.step, self.loop, self.peak = step, n * step + pause, peak
        self.css = ""
        self._names: set[str] = set()

    def cls(self, steps: float = 1) -> str:
        name = f"ph{str(steps).replace('.', '_')}"
        if name not in self._names:
            self._names.add(name)
            on = steps * self.step / self.loop * 100
            fade = min(1.5, on * 0.3)
            self.css += (
                f"@keyframes {name}{{0%{{opacity:0}}{fade:.2f}%{{opacity:{self.peak}}}"
                f"{on:.2f}%{{opacity:{self.peak}}}{on + fade:.2f}%{{opacity:0}}100%{{opacity:0}}}}"
                f".{name}{{opacity:0;animation:{name} {self.loop:.2f}s linear infinite}}"
            )
        return f"cur {name}"

    def at(self, index: float) -> str:
        return f"animation-delay:{index * self.step:.2f}s"


class Plate:
    def __init__(
        self, title: str, height: float, desc: str, big: tuple[str, str] | None = None
    ) -> None:
        self.title, self.height, self.desc, self.big = title, height, desc, big
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.extra: dict[str, tuple[str, str]] = {}  # class -> (light fill, dark fill)
        self.legend = False
        self.cursor: Cursor | None = None

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def _palette(self, pal: dict[str, str], col: int) -> str:
        rules = [f".f-{k}{{fill:{v}}}.s-{k}{{stroke:{v}}}" for k, v in pal.items()]
        rules += [f".{k}{{fill:{v[col]}}}" for k, v in self.extra.items()]
        return "".join(rules)

    def render(self) -> str:
        h = num(float(self.height))
        css = (
            BASE_CSS
            + self._palette(LIGHT, 0)
            + "\n@media (prefers-color-scheme:dark){"
            + self._palette(DARK, 1)
            + "}\n"
            + (self.cursor.css if self.cursor else "")
        )
        head = [
            rect(0.5, 0.5, W - 1, self.height - 1, "f-plate s-rule", rx=6),
            text(20, 40, self.title, "f-ink bb", 23),
        ]
        if self.big:
            kind, s = self.big
            gw = 30 * 0.74
            g, _ = glyph(kind, W - 20 - gw, 42, 30)
            head += [
                g,
                text(W - 30 - gw, 42, s, "f-ink bb", 30, "end"),
            ]
        elif self.legend:
            head.append(legend(W - 20, 38, ARMS))
        defs = el("defs", "".join(self.defs)) if self.defs else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{defs}{''.join(head)}{''.join(self.parts)}</svg>\n"
        )


# ---------------------------------------------------------------- shared marks


def dot_panel(
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
    paired: bool = True,
    lower_better: bool = True,
    ticks: list[float] | None = None,
    tick_fmt=None,
    tick_labels: bool = True,
    labels: str = "two",
    r: float = 4.5,
    boots: list[float] | None = None,
    mark_glyph: bool = False,
    motion: tuple[str, ...] = ("connector",),
) -> str:
    """Draw base and candidate as beeswarm dot columns on the metric's own axis.

    The ±Δ band sits around the base median. The bracket beside the candidate column is
    the CI of the shift, drawn where it puts the candidate median (base median x shift).
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
    out.append(rect(px + 2, top, x1 - px - 4, bot - top, "f-band s-bandEdge", stroke_width=1))
    pb, pc = [ys(v) for v in base], [ys(v) for v in cand]
    ob, oc = swarm(pb, r), swarm(pc, r)
    mark, _, _ = VERDICT[kind]
    if paired:
        for i in range(len(base)):
            better = (cand[i] < base[i]) == lower_better
            xa, xb = cb + ob[i], cc + oc[i]
            out.append(
                line(
                    xa,
                    pb[i],
                    xb,
                    pc[i],
                    "s-cand" if better else "s-worse",
                    1.2,
                    stroke_opacity=0.3 if better else 0.6,
                )
            )
            if "pairs" in motion:  # dashes drift from the base run to its candidate run
                tok = "cand" if better else "worse"
                out.append(line(xa, pb[i], xb, pc[i], f"s-{tok} shimmer", 1.6, stroke_opacity=0.65))
    out += [
        circle(cb + o, p, r, "f-base s-plate", stroke_width=1) for o, p in zip(ob, pb, strict=True)
    ]
    out += [
        circle(cc + o, p, r, "f-cand s-plate", stroke_width=1) for o, p in zip(oc, pc, strict=True)
    ]
    hws = [min(max(abs(o) for o in offs) + r + 5, wid * 0.15) for offs in (ob, oc)]
    moved = kind in {"improved", "regressed"} and "connector" in motion
    out.append(
        line(
            cb + hws[0] + 4,
            ys(bmed),
            cc - hws[1] - 4,
            ys(cmed),
            f"s-{mark} {'flow' if moved else 'still'}",
            2.5,
            stroke_opacity=1 if moved else 0.6,
        )
    )
    for (cx, med, tok), hw in zip(((cb, bmed, "base"), (cc, cmed, "cand")), hws, strict=True):
        bar = line(cx - hw, ys(med), cx + hw, ys(med), "s-plate", 9, stroke_linecap="round")
        bar += line(cx - hw, ys(med), cx + hw, ys(med), f"s-{tok}", 5, stroke_linecap="round")
        out.append(bar)
    bx = min(cc + max(abs(o) for o in oc) + r + 14, x1 - 8)
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


def run_rows(
    x0: float,
    y0: float,
    rows: list[tuple[str, str]],
    *,
    cell: float = 16,
    h: float = 12,
    gap: float = 3,
    pair_gap: float = 6,
    pitch: float = 22,
    label_w: float = 58,
    pairs: bool = True,
    cursor: Cursor | None = None,
    start: int = 0,
) -> str:
    """Draw one thin row of run-order squares per VM: "A" is base (grey), "B" candidate.

    With a cursor, the row being played is tinted (runs group by VM) and each square
    gets a ring when its run plays.
    """
    out = []
    idx = start
    for r, (label, seq) in enumerate(rows):
        y = y0 + r * pitch
        if cursor:
            span = len(seq) * (cell + gap) + (len(seq) // 2) * pair_gap * pairs + 8
            out.append(
                rect(
                    x0 - 6,
                    y - 4,
                    label_w + span,
                    h + 8,
                    f"f-ink {cursor.cls(len(seq))}",
                    rx=4,
                    fill_opacity=0.12,
                    style=cursor.at(idx),
                )
            )
        out.append(text(x0, y + h, label, "mono f-muted"))
        for i, a in enumerate(seq):
            x = x0 + label_w + i * (cell + gap) + ((i // 2) * pair_gap if pairs else 0)
            out.append(rect(x, y, cell, h, "f-base" if a == "A" else "f-cand", rx=2))
            if cursor:
                out.append(
                    rect(
                        x - 2.5,
                        y - 2.5,
                        cell + 5,
                        h + 5,
                        f"s-ink {cursor.cls()}",
                        rx=3,
                        fill="none",
                        stroke_width=1.8,
                        style=cursor.at(idx),
                    )
                )
            idx += 1
    return "".join(out)


def abba_rows(pairs: list[Pair]) -> list[tuple[str, str]]:
    return [(f"VM {s + 1}", "".join(p.order for p in pairs if p.shard == s)) for s in range(4)]


def axis_range(vals: list[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return lo - span * pad, hi + span * pad


# ---------------------------------------------------------------- plates


def plate_g1() -> Plate:
    k_plan = verdict(-C90[1], -C90[0], MARGIN)
    k_track = verdict(-TRACK_C90[1], -TRACK_C90[0], MARGIN)
    desc = (
        f"planning_time {fmt(pct(EST))} % (90 % CI {fmt(pct(C90[0]))} to {fmt(pct(C90[1]))}), "
        f"improved; task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}, {TS_TXT}, inconclusive; "
        f"tracking_error_rms "
        f"{fmt(pct(TRACK_EST))} %, no change. Paired ABBA, 20 pairs on 4 VMs."
    )
    pl = Plate(f"Planning is {abs(pct(EST)):.0f} % faster", 540, desc)
    cur = pl.cursor = Cursor(40)
    panels = [
        ("planning_time · s", f"{fmt(pct(EST))} %", k_plan, PAIRS, C90, EST),
        ("task_success", TS_TXT, TS_KIND, None, None, None),
        ("tracking_error · mm", f"{fmt(pct(TRACK_EST))} %", k_track, TRACK, TRACK_C90, TRACK_EST),
    ]
    for i, (name, big, kind, pairs, ci, est) in enumerate(panels):
        x0 = 20 + i * 258
        x1 = x0 + 244
        g, _ = glyph(kind, x0 + len(big) * 15.5 + 8, 116, 26)
        pl.add(text(x0, 80, name, "mono f-ink2"), text(x0, 116, big, "f-ink bb", 28), g)
        y0, y1 = 140, 360
        if pairs is None:
            pl.add(_binary_panel(x0, x1, y0, y1))
            continue
        lo, hi = axis_range([p.base for p in pairs] + [p.cand for p in pairs])
        pl.add(
            dot_panel(
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
            )
        )
    pl.add(
        run_rows(20, 438, abba_rows(PAIRS), cursor=cur), text(308, 450, "run order →", "f-muted")
    )
    return pl


def _binary_panel(x0: float, x1: float, y0: float, y1: float) -> str:
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
            else:
                out.append(rect(x, y, size, size, f"f-{tok}", rx=3))
                if tok == "cand" and i == 17:  # the run that changed is outlined
                    out.append(
                        rect(
                            x - 3,
                            y - 3,
                            size + 6,
                            size + 6,
                            "s-better",
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


def plate_design() -> Plate:
    desc = (
        "This run: paired ABBA on 4 VMs, 5 pairs each, each pair back to back on one VM. "
        "Blocked contrast: all base then all candidate on one VM."
    )
    pl = Plate("Paired ABBA on 4 VMs", 290, desc)
    pl.legend = True
    cur = pl.cursor = Cursor(60, step=0.35)
    # drift lands where the blocked row turns from base to candidate: that edge glows
    edge = 20 + 90 + 10 * 26 - 2
    pl.add(
        rect(edge - 4, 202, 8, 32, f"f-unsure {cur.cls(4)}", rx=4, style=cur.at(49.5)),
        run_rows(
            20,
            80,
            abba_rows(PAIRS),
            cell=22,
            h=16,
            gap=4,
            pair_gap=10,
            pitch=28,
            label_w=90,
            cursor=cur,
        ),
        run_rows(
            20,
            210,
            [("blocked", "A" * 10 + "B" * 10)],
            cell=22,
            h=16,
            gap=4,
            pairs=False,
            label_w=90,
            cursor=cur,
            start=40,
        ),
        line(110, 258, 600, 258, "s-muted"),
        el("path", d="M600 253L609 258L600 263Z", cls="f-muted"),
        text(618, 263, "run order", "f-muted"),
    )
    return pl


def plate_g2() -> Plate:
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
            [p.base / quant([q.base for q in TRACK], 0.5) for p in TRACK],
            [p.cand / quant([q.base for q in TRACK], 0.5) for p in TRACK],
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
            continue  # drawn above from TRACK, as in G1; the draws keep the other rows' streams
        rows.append((name, d, [b / med for b in base], [c / med for c in cand], m, (lo_ci, hi_ci)))
    rows.sort(key=lambda r: r[4])
    kinds = [
        verdict(a0, a1, MARGIN) if d == "max" else verdict(-a1, -a0, MARGIN)
        for _, d, _, _, _, (a0, a1) in rows
    ]
    n_imp = kinds.count("improved")
    n_un = kinds.count("unsure") + kinds.count("regressed")
    n_eq = kinds.count("equiv") + kinds.count("small")
    desc = "12 metrics, every sample as % of its base median, ±5 % band: " + "; ".join(
        f"{r[0]} {fmt(pct(r[4]))} %" for r in rows
    )
    pl = Plate(f"{n_imp} better, {n_un} unclear, {n_eq} same", 616, desc)
    lo, hi = 0.68, 1.34
    ticks = [0.8, 1.0, 1.2]

    def tf(t: float) -> str:
        return "0" if t == 1.0 else f"{fmt((t - 1) * 100, 0)} %"

    left, pw, ph, pitch = 70, 178, 150, 176
    for i, ((name, d, base, cand, m, ci), kind) in enumerate(zip(rows, kinds, strict=True)):
        r, k = divmod(i, 4)
        x0, y = left + k * pw, 66 + r * pitch
        pl.add(text(x0 + 4, y + 18, name, "mono f-ink2"))
        if k == 0:
            for t in ticks:
                yt = y + ph - (t - lo) / (hi - lo) * (ph - 32)
                pl.add(text(left - 6, yt + 5, tf(t), "mono f-muted", FS, "end"))
        pl.add(
            dot_panel(
                x0=x0,
                x1=x0 + pw - 8,
                y0=y + 32,
                y1=y + ph,
                base=base,
                cand=cand,
                lo=lo,
                hi=hi,
                ci=ci,
                est=m,
                kind=kind,
                lower_better=d == "min",
                ticks=ticks,
                tick_labels=False,
                labels="none",
                r=2.6,
                mark_glyph=True,
            )
        )
    pl.add(legend(W - 20, 600, [*ARMS, ("f-band", "±5 % of base median")]))
    return pl


def plate_g3() -> Plate:
    kind = verdict(-C90[1], -C90[0], MARGIN)
    desc = (
        f"planning_time, 20 ABBA pairs on 4 VMs: {sum(p.cand < p.base for p in PAIRS)} of 20 "
        f"pairs faster. Effect {fmt(pct(EST))} %, 90 % CI [{fmt(pct(C90[0]))}, "
        f"{fmt(pct(C90[1]))}] %."
    )
    pl = Plate(f"Planning is {abs(pct(EST)):.0f} % faster", 480, desc, (kind, f"{fmt(pct(EST))} %"))
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    pl.add(
        dot_panel(
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
            motion=("connector", "pairs"),
        ),
        run_rows(540, 120, abba_rows(PAIRS), cell=14, gap=3, pair_gap=5, pitch=24, label_w=54),
        text(594, 236, "run order →", "f-muted"),
    )
    return pl


def plate_g4() -> Plate:
    n = 60
    arm_a: list[float] = []
    arm_b: list[float] = []
    for _ in range(n):
        va = math.exp(math.log(0.30) + 0.25 * RNG.norm())
        arm_a.append(va + (0.28 + 0.15 * RNG.rnd() if RNG.rnd() < 0.2 else 0))
        vb = math.exp(math.log(0.30) + 0.25 * RNG.norm())
        arm_b.append(vb + (0.04 + 0.06 * RNG.rnd() if RNG.rnd() < 0.2 else 0))
    dec = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    shifts = []
    for p in dec:
        diffs = []
        for _ in range(600):
            ra = [arm_a[math.floor(RNG.rnd() * n)] for _ in arm_a]
            rb = [arm_b[math.floor(RNG.rnd() * n)] for _ in arm_b]
            diffs.append(quant(rb, p) - quant(ra, p))
        shifts.append((quant(arm_b, p) - quant(arm_a, p), quant(diffs, 0.025), quant(diffs, 0.975)))
    p90 = shifts[-1]
    desc = (
        f"Latency, 60 runs per arm. Median shift {fmt(shifts[4][0] * 1000, 0)} ms (CI holds 0); "
        f"p90 shift {fmt(p90[0] * 1000, 0)} ms, 95 % CI [{fmt(p90[1] * 1000, 0)}, "
        f"{fmt(p90[2] * 1000, 0)}]."
    )
    big = ("improved", f"p90 {fmt(p90[0] * 1000, 0)} ms")
    pl = Plate("The tail moved, median held", 590, desc, big)
    x0, x1, lo, hi = 140, 780, 0.1, 1.0

    def xs(v: float) -> float:
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    for v in (0.2, 0.4, 0.6, 0.8):
        pl.add(
            line(xs(v), 80, xs(v), 372, "s-grid"),
            text(xs(v), 394, f"{v:.1f} s", "mono f-muted", FS, "middle"),
        )
    bmed = quant(arm_a, 0.5)
    b_lo, b_hi = xs(bmed / math.exp(MARGIN)), xs(bmed * math.exp(MARGIN))
    pl.add(rect(b_lo, 80, b_hi - b_lo, 292, "f-band s-bandEdge", stroke_width=1))
    for arr, yb, tok, name in ((arm_a, 170, "base", "base"), (arm_b, 320, "cand", "candidate")):
        bw, pts = 0.03, []
        for k in range(121):
            x = lo + k / 120 * (hi - lo)
            pts.append((x, sum(math.exp(-(((x - a) / bw) ** 2) / 2) for a in arr)))
        m = max(p[1] for p in pts)
        d = f"M{num(xs(lo))} {yb}" + "".join(
            f"L{num(xs(x))} {num(yb - v / m * 70)}" for x, v in pts
        )
        pl.add(
            el(
                "path",
                d=d + f"L{num(xs(hi))} {yb}Z",
                cls=f"f-{tok} s-{tok}",
                fill_opacity=0.22,
                stroke_width=1.5,
            )
        )
        offs = swarm([xs(a) for a in arr], 3, one_sided=True)
        pl.add(
            *(
                circle(xs(a), yb + 7 + o, 3, f"f-{tok} s-plate", stroke_width=0.8)
                for a, o in zip(arr, offs, strict=True)
            )
        )
        md = quant(arr, 0.5)
        pl.add(
            line(xs(md), yb - 22, xs(md), yb + 2, "s-plate", 9, stroke_linecap="round"),
            line(xs(md), yb - 22, xs(md), yb + 2, f"s-{tok}", 5, stroke_linecap="round"),
            text(20, yb - 6, name, "f-ink b"),
            text(20, yb + 14, f"n={len(arr)}", "mono f-muted"),
        )
    sy0, sy1, dlo, dhi = 440, 545, -0.38, 0.08

    def ys(v: float) -> float:
        return sy1 - (v - dlo) / (dhi - dlo) * (sy1 - sy0)

    pl.add(text(20, ys(0) + 5, "shift", "f-ink b"), text(20, ys(0) + 25, "ms", "mono f-muted"))
    for v in (-0.3, -0.2, -0.1, 0):
        pl.add(
            line(x0, ys(v), x1, ys(v), "s-muted" if v == 0 else "s-grid"),
            text(x0 - 8, ys(v) + 5, "0" if v == 0 else fmt(v * 1000, 0), "mono f-muted", FS, "end"),
        )
    step = (x1 - x0) / len(dec)
    for k, (dv, lo_ci, hi_ci) in enumerate(shifts):
        x = x0 + (k + 0.5) * step
        sig = hi_ci < 0 or lo_ci > 0
        tok = ("better" if hi_ci < 0 else "worse") if sig else "muted"
        mark = line(
            x, ys(max(lo_ci, dlo)), x, ys(min(hi_ci, dhi)), f"s-{tok}", 3, stroke_linecap="round"
        )
        mark += circle(
            x, ys(dv), 6, f"f-{tok} s-{tok}" if sig else f"f-plate s-{tok}", stroke_width=2
        )
        pl.add(
            mark,
            text(x, sy1 + 24, f"p{round(dec[k] * 100)}", "mono f-muted", FS, "middle"),
        )
    return pl


def plate_g5() -> Plate:
    desc = (
        f"task_success {TS_BASE}/{TS_N} to {TS_CAND}/{TS_N}: {TS_TXT}, 90 % CI {TS_CI_TXT}, "
        f"inconclusive. required_sigkill: base {SK_BASE}/{SK_N} killed, candidate "
        f"{SK_CAND}/{SK_N}, true rate at most {SK_BOUND * 100:.1f} %: improved."
    )
    pl = Plate("Flake fixed; success still unclear", 340, desc)

    def waffle(
        x0: float,
        y0: float,
        n: int,
        fails: int,
        tok: str,
        cols: int,
        c: float,
        changed: set[int],
    ) -> None:
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
            else:
                pl.add(rect(x, y, c, c, f"f-{tok}", rx=3))
                if i in changed:  # a run that failed on base and passed here is outlined
                    pl.add(
                        rect(
                            x - 3,
                            y - 3,
                            c + 6,
                            c + 6,
                            "s-better",
                            rx=5,
                            fill="none",
                            stroke_width=2,
                        )
                    )

    g, _ = glyph("unsure", 138, 120, 26)
    pl.add(
        text(20, 82, "task_success", "mono f-ink2"),
        text(20, 120, TS_TXT, "f-ink bb", 28),
        g,
        text(20, 165, "base"),
        text(20, 215, "candidate"),
    )
    waffle(110, 146, TS_N, TS_N - TS_BASE, "base", 9, 18, set())
    waffle(110, 196, TS_N, TS_N - TS_CAND, "cand", 9, 18, {17})
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
    waffle(fx + 90, 150, SK_N, SK_BASE, "base", 15, 14, set())
    waffle(fx + 90, 200, SK_N, SK_CAND, "cand", 15, 14, set(range(SK_N - SK_BASE, SK_N)))
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


def plate_g6() -> Plate:
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
    pl = Plate("Faster above 0.6 m/s", 460, desc, (last[5], f"{fmt(pct(last[3]))} %"))
    x0, x1, y0, y1, lo, hi = 74, 790, 80, 370, 0.95, 2.95

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    for t in (1.0, 1.5, 2.0, 2.5):
        pl.add(
            line(x0, ys(t), x1, ys(t), "s-grid"),
            text(x0 - 8, ys(t) + 5, f"{t:.1f} s", "mono f-muted", FS, "end"),
        )
    step = (x1 - x0) / len(sp)
    # candidate medians joined across speeds; the line is darker where the point is beyond ±Δ
    meds = [(x0 + (k + 0.5) * step + 10, ys(quant(g[2], 0.5)), g[5]) for k, g in enumerate(groups)]
    for (xa, ya, ka), (xb, yb, kb) in itertools.pairwise(meds):
        beyond = ka == kb == "improved"
        pl.add(
            line(
                xa,
                ya,
                xb,
                yb,
                "s-cand still",
                2,
                stroke_opacity=0.9 if beyond else 0.45,
            )
        )
    for k, (v, base, cand, m, ci, kind) in enumerate(groups):
        gx = x0 + (k + 0.5) * step
        g, _ = glyph(kind, gx - 4, ys(max(base + cand)) - 16, FS + 2)
        pl.add(
            dot_panel(
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
                ticks=[],
                tick_labels=False,
                labels="none",
                r=3.4,
            ),
            g,
            text(gx - 6, y1 + 26, f"{v:.1f}", "mono f-muted", FS, "middle"),
        )
    pl.add(
        text((x0 + x1) / 2, y1 + 54, "speed (m/s)", "f-ink2", FS, "middle"),
        legend(W - 20, y1 + 54, ARMS),
    )
    return pl


def _srgb_to_oklab(hx: str) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(hx[i : i + 2], 16) / 255) for i in (1, 3, 5))
    lc = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    mc = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    sc = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc,
        1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc,
        0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc,
    )


def _oklab_to_srgb(lab: tuple[float, float, float]) -> str:
    big_l, a, b = lab
    lc = (big_l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    mc = (big_l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    sc = (big_l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * lc - 3.3077115913 * mc + 0.2309699292 * sc,
        -1.2684380046 * lc + 2.6097574011 * mc - 0.3413193965 * sc,
        -0.0041960863 * lc - 0.7034186147 * mc + 1.7076147010 * sc,
    )

    def gam(c: float) -> int:
        c = min(1.0, max(0.0, c))
        v = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return round(v * 255)

    return "#" + "".join(f"{gam(c):02X}" for c in rgb)


def mix(pole: str, other: str, share: float) -> str:
    """Mix like CSS ``color-mix(in oklab, pole share, other)``."""
    p, o = _srgb_to_oklab(pole), _srgb_to_oklab(other)
    return _oklab_to_srgb(tuple(share * a + (1 - share) * b for a, b in zip(p, o, strict=True)))


def _hatch(x: float, y: float, w: float, h: float, cid: str) -> tuple[str, str]:
    """Return a clip path and diagonal hatch lines for a w x h box at (x, y)."""
    clip = el("clipPath", rect(x, y, w, h, "", rx=3), id=cid)
    lines = "".join(
        line(x + j, y + h, x + j + h, y, "s-muted", 1.4, stroke_opacity=0.5)
        for j in range(-int(h) - 8, int(w) + 8, 8)
    )
    return clip, el("g", lines, clip_path=f"url(#{cid})")


def plate_g7() -> Plate:
    sp, mass = [0.4, 0.8, 1.2, 1.6], [0.5, 1, 2, 4, 6]
    cells = []
    for r, m in enumerate(mass):
        for k, v in enumerate(sp):
            p = -(m * v * 2.2) + 1.5
            half = 2.2 + 0.9 / (r + 1)
            unsure = not ((p + half) < -5 or (p - half) > 5 or (abs(p) + half < 5))
            kind = (
                "unsure"
                if unsure
                else ("improved" if p < -5 else "regressed" if p > 5 else "equiv")
            )
            cells.append((r, k, p, kind))
    n_un = sum(c[3] == "unsure" for c in cells)
    best = min(cells, key=lambda c: c[2])
    desc = (
        f"Illustrative cell values from a formula, not simulated runs. "
        f"cycle_time % change over speed and payload, 20 cells, 6 paired repeats each: best "
        f"{fmt(best[2], 0)} % at {sp[best[1]]} m/s and {mass[best[0]]} kg; {n_un} cells "
        f"inconclusive."
    )
    pl = Plate("Gain is in heavy, fast picks", 420, desc, ("improved", f"{fmt(best[2], 0)} %"))

    def colour_class(p: float) -> str:
        t = min(1.0, abs(p) / 15)
        share = (15 + t * 85) / 100
        pole = "cand" if p < 0 else "worse"
        pair = (mix(LIGHT[pole], LIGHT["chip"], share), mix(DARK[pole], DARK["chip"], share))
        for name, val in pl.extra.items():
            if val == pair:
                return name
        name = f"h{len(pl.extra)}"
        pl.extra[name] = pair
        return name

    x0, y0, cw, ch = 100, 76, 110, 58
    for r, m in enumerate(mass):
        pl.add(text(x0 - 10, y0 + r * ch + ch / 2 + 5, f"{m} kg", "mono f-muted", FS, "end"))
    for i, (r, k, p, kind) in enumerate(cells):
        x, y = x0 + k * cw, y0 + r * ch
        unsure = kind == "unsure"
        if unsure:
            clip, hatch = _hatch(x + 1, y + 1, cw - 2, ch - 2, f"c{i}")
            pl.defs.append(clip)
            pl.add(rect(x + 1, y + 1, cw - 2, ch - 2, "f-plate s-rule", rx=3), hatch)
        else:
            pl.add(rect(x + 1, y + 1, cw - 2, ch - 2, colour_class(p), rx=3))
        dark = abs(p) > 9 and not unsure
        tok = "white" if dark else "ink"
        label = "0 %" if round(p) == 0 else f"{fmt(p, 0)} %"
        tw = len(label) * FS * 0.6
        g, gw = glyph(kind, 0, 0, FS)
        if dark:
            g = g.replace(f"f-{VERDICT[kind][1]}", "f-white")
        sx = x + cw / 2 - (gw + 5 + tw) / 2
        pl.add(
            el("g", g, transform=f"translate({num(sx)},{num(y + ch / 2 + 2)})"),
            text(sx + gw + 5, y + ch / 2 + 2, label, f"mono f-{tok}", FS, font_weight=500),
        )
        pl.add(  # the six paired repeats behind this cell
            *(
                circle(x + cw - 34 + j * 5, y + ch - 9, 1.6, f"f-{tok}", fill_opacity=0.6)
                for j in range(6)
            )
        )
    for k, v in enumerate(sp):
        pl.add(
            text(
                x0 + k * cw + cw / 2,
                y0 + len(mass) * ch + 24,
                f"{v} m/s",
                "mono f-muted",
                FS,
                "middle",
            )
        )
    lx, ly = 580, 96
    pl.add(*(rect(lx + i * 6, ly, 6.5, 18, colour_class(-15 + i)) for i in range(31)))
    for p in (-15, 0, 15):
        lab = "0" if p == 0 else f"{fmt(p, 0)} %"
        pl.add(text(lx + (p + 15) * 6 + 3, ly + 40, lab, "mono f-muted", FS, "middle"))
    clip, hatch = _hatch(lx, ly + 72, 34, 26, "lg")
    pl.defs.append(clip)
    g, _ = glyph("unsure", lx + 44, ly + 92, FS + 2)
    pl.add(rect(lx, ly + 72, 34, 26, "f-plate s-rule", rx=3, stroke_width=1), hatch, g)
    return pl


def plate_g8() -> Plate:
    mde = pct(PW_MDE)
    desc = (
        f"Underpowered: n = {PW_N} per arm can see {mde:.1f} % or more; the claim needs 5 %. "
        f"About {PW_NEED} runs per arm reach it."
    )
    pl = Plate("Too few runs for ±5 %", 270, desc, ("unsure", f"MDE {mde:.1f} %"))
    x0, x1 = 40, 760

    def sc(p: float) -> float:
        return x0 + p / 14 * (x1 - x0)

    pl.add(
        rect(x0, 96, x1 - x0, 24, "f-chip", rx=4),
        rect(x0, 96, sc(5) - x0, 24, "f-band s-bandEdge", rx=4),
        rect(x0, 102, sc(mde) - x0, 12, "f-unsure", rx=6),
        # more runs close this gap: dashes flow from the MDE toward the margin
        line(sc(mde) - 6, 108, sc(5) + 3, 108, "s-plate flow overlay", 2.5),
        line(sc(5), 88, sc(5), 128, "s-ink", 2.5),
        text(sc(5), 82, "±Δ", "f-ink b", FS, "middle"),
        text(sc(mde), 82, "MDE", "f-ink b", FS, "middle"),
        *(text(sc(p), 146, f"{p} %", "mono f-muted", FS, "middle") for p in range(0, 15, 2)),
        text(x0, 196, "now"),
        text(x0, 232, "needed"),
    )
    for i in range(PW_NEED):
        x = 130 + i * 20
        if i < PW_N:
            pl.add(rect(x, 182, 16, 16, "f-cand", rx=2), rect(x, 218, 16, 16, "f-cand", rx=2))
        else:
            pl.add(rect(x + 1, 219, 14, 14, "s-cand", rx=2, fill="none", stroke_width=2))
    pl.add(
        text(130 + PW_N * 20 + 6, 196, str(PW_N), "mono f-muted"),
        text(130 + PW_NEED * 20 + 6, 232, str(PW_NEED), "mono f-muted"),
    )
    return pl


def plate_g9() -> Plate:
    desc = (
        f"planning_time against run order, 40 runs on 4 VMs, with an assumed A/A noise floor "
        f"(±{AA_BAND * 100:.0f} %). Slope per run: base {fmt(pct(DRIFT['A'][0]), 2)} %, "
        f"candidate {fmt(pct(DRIFT['B'][0]), 2)} %."
    )
    pl = Plate("No drift across run order", 340, desc)
    pl.legend = True
    x0, x1, y0, y1, n, lo, hi = 70, 780, 74, 280, 40, 0.17, 0.64

    def xs(i: float) -> float:
        return x0 + i / (n - 1) * (x1 - x0)

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    for v in (0.2, 0.3, 0.4, 0.5, 0.6):
        pl.add(
            line(x0, ys(v), x1, ys(v), "s-grid"),
            text(x0 - 8, ys(v) + 5, f"{v:.1f}", "mono f-muted", FS, "end"),
        )
    med = quant([p.base for p in PAIRS], 0.5)
    top, bot = ys(med * (1 + AA_BAND)), ys(med * (1 - AA_BAND))
    pl.add(rect(x0, top, x1 - x0, bot - top, "f-band s-bandEdge", stroke_width=2))
    i = 0
    for p in PAIRS:
        seq = [("A", p.base), ("B", p.cand)] if p.order == "AB" else [("B", p.cand), ("A", p.base)]
        for a, v in seq:
            cls = f"f-{'base' if a == 'A' else 'cand'} s-plate"
            pl.add(
                circle(xs(i), ys(v), 5, cls, stroke_width=1.5),
            )
            i += 1
    for k in range(1, 4):
        x = (xs(k * 10 - 1) + xs(k * 10)) / 2
        pl.add(line(x, y0, x, y1, "s-rule", 1.5, stroke_dasharray="4 4"))
    for k in range(4):
        cx = (xs(k * 10) + xs(k * 10 + 9)) / 2
        pl.add(text(cx, y1 + 26, f"VM {k + 1}", "mono f-muted", FS, "middle"))
    pl.add(text(x0, y1 + 50, "run order →", "f-muted"), text(20, y0 + 4, "s", "mono f-muted"))
    return pl


def plate_dont() -> Plate:
    desc = (
        "Charts the report does not draw: radar charts, bars of means with error bars, and "
        "'p > 0.05, unchanged'."
    )
    pl = Plate("Charts we do not draw", 270, desc)

    def radar() -> str:
        cx, cy, r, k = 150, 80, 62, 6

        def poly(vals: list[float]) -> str:
            pts = []
            for i in range(k):
                a = i / k * 2 * math.pi - math.pi / 2
                px, py = cx + math.cos(a) * r * vals[i], cy + math.sin(a) * r * vals[i]
                pts.append(f"{'L' if i else 'M'}{num(px)} {num(py)}")
            return "".join(pts) + "Z"

        out = [el("path", d=poly([ring / 3] * k), cls="s-grid", fill="none") for ring in (1, 2, 3)]
        for vals, tok in (
            ([1, 0.8, 0.9, 1, 0.7, 1], "base"),
            ([0.9, 1, 0.6, 0.95, 1, 0.8], "cand"),
        ):
            out.append(
                el(
                    "path",
                    d=poly(vals),
                    cls=f"f-{tok} s-{tok}",
                    fill_opacity=0.18,
                    stroke_width=1.5,
                )
            )
        return "".join(out)

    def bars() -> str:
        out = [line(40, 140, 280, 140, "s-muted")]
        for x, tok, h in ((90, "base", 95), (190, "cand", 80)):
            out += [
                rect(x - 30, 140 - h, 60, h, f"f-{tok}", rx=2),
                line(x, 140 - h - 18, x, 140 - h + 18, "s-ink", 1.5),
                line(x - 8, 140 - h - 18, x + 8, 140 - h - 18, "s-ink", 1.5),
            ]
        return "".join(out)

    def pval() -> str:
        def sc(v: float) -> float:
            return 150 + v * 9

        g, _ = glyph("unsure", 143, 40, 22)
        return "".join(
            [
                rect(sc(-5), 55, sc(5) - sc(-5), 40, "f-band"),
                line(sc(0), 50, sc(0), 100, "s-muted"),
                line(sc(-12), 75, sc(10), 75, "s-unsure", 5, stroke_linecap="round"),
                circle(sc(-1), 75, 6, "f-plate s-unsure", stroke_width=2.5),
                g,
            ]
        )

    cards = (("Radar chart", radar), ("Bar of means", bars), ("“p > 0.05, unchanged”", pval))
    for i, (title, draw) in enumerate(cards):
        ox = 20 + i * 260
        cross = el("path", d=f"M{ox + 6} 233l10 10m0 -10l-10 10", cls="s-tworse", stroke_width=2.4)
        pl.add(
            el("g", draw(), transform=f"translate({ox},64) scale(0.8)"),
            cross,
            text(ox + 26, 244, title, "f-tworse b", 16),
        )
    return pl


PLATES = {
    "g1_scorecard.svg": plate_g1,
    "d_design_strip.svg": plate_design,
    "g2_forest.svg": plate_g2,
    "g3_estimation.svg": plate_g3,
    "g4_raincloud_shift.svg": plate_g4,
    "g5_waffle.svg": plate_g5,
    "g6_sweep.svg": plate_g6,
    "g7_heatmap.svg": plate_g7,
    "g8_power.svg": plate_g8,
    "g9_diagnostics.svg": plate_g9,
    "x_not_drawn.svg": plate_dont,
}


def facts() -> dict[str, str]:
    """Return every number that the PR captions quote, from the same data as the plates."""
    p = pct
    return {
        "planning_time": f"{fmt(p(EST))} % 90% BCa [{fmt(p(C90[0]))}, {fmt(p(C90[1]))}]",
        "pairs_faster": f"{sum(q.cand < q.base for q in PAIRS)}/{len(PAIRS)}",
        "wilcoxon_p": f"{WILCOXON_P:.2g}",
        "tracking_error": f"{fmt(p(TRACK_EST))} % 90% BCa [{fmt(p(TRACK_C90[0]))}, "
        f"{fmt(p(TRACK_C90[1]))}]",
        "task_success": f"{TS_TXT} Newcombe 90% {TS_CI_TXT} Barnard p={TS_P:.2f} "
        f"MDE={TS_MDE * 100:.0f} pp {TS_KIND}",
        "sigkill": f"{SK_BASE}/{SK_N}->{SK_CAND}/{SK_N} bound {SK_BOUND * 100:.1f} % runs {SK_RUNS}",
        "power": f"n={PW_N} sd={PW_SD} MDE={pct(PW_MDE):.1f} % need={PW_NEED}",
        "drift": "; ".join(
            f"{a} {fmt(p(b), 2)} [{fmt(p(lo), 2)}, {fmt(p(hi), 2)}] %/run"
            for a, (b, lo, hi) in DRIFT.items()
        ),
        "vm2_slow": f"{VM2_SLOW * 100:.0f} %",
    }


def main() -> None:
    if "--facts" in sys.argv:
        for k, v in facts().items():
            sys.stdout.write(f"{k}: {v}\n")
        return
    # G4 draws from the shared RNG stream after the planning_time bootstrap.
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
