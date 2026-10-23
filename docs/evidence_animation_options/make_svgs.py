"""Write the animation options A-H for the statistical-evidence plates as SVG files.

Each plate tries one kind of motion, so the options can be compared and combined. The
data are seeded, so every run writes the same files; the paired runs are the ones of the
evidence demo in #1188, and the traces, paths and commit history are synthetic. The script
uses only the standard library:

    python docs/evidence_animation_options/make_svgs.py

Rules that every plate keeps: the data are on screen for at least 80 % of each loop, a
loop is 6 s or less, the motion carries one idea, and every frame is a correct chart
except while a labelled transform runs. Each SVG has a light and a dark palette
(``prefers-color-scheme``); ``prefers-reduced-motion`` shows the most informative still.
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

# Dash flow runs at 3 s, so it shares a 6 s loop with the morphs and the blink.
BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
@keyframes drift{{to{{stroke-dashoffset:-24}}}}
@keyframes flow{{to{{stroke-dashoffset:-20}}}}
.shimmer{{stroke-dasharray:4 8;animation:drift 3s linear infinite}}
.flow{{stroke-dasharray:6 4;animation:flow 3s linear infinite}}
.still{{stroke-dasharray:6 4}}
"""
# Reduced motion: every element sits at its own attributes, the most informative still.
REDUCED_CSS = """
@media (prefers-reduced-motion:reduce){
.anim,.flow,.shimmer{animation:none!important}.shimmer{display:none}
.rm-off{opacity:0!important}.rm-on{opacity:1!important}}
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


def signed(v: float) -> str:
    """Format a tick value with a real minus sign and a plus sign."""
    sign = "+" if v > 0 else "−" if v < 0 else ""
    return f"{sign}{abs(v):g}"


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


Z = NormalDist()
Z90 = Z.inv_cdf(0.95)  # two-sided 90 %


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
    coords: dict[str, object] | None = None,
) -> str:
    """Draw base and candidate as beeswarm dot columns on the metric's own axis.

    The ±Δ band sits around the base median. The bracket beside the candidate column is
    the CI of the shift, drawn where it puts the candidate median (base median x shift).
    When coords is given, it receives the dot centres and the axis mapping, so a caller
    can move copies of the dots.
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
        circle(cb + o, p, r, "f-base s-plate data", stroke_width=1)
        for o, p in zip(ob, pb, strict=True)
    ]
    out += [
        circle(cc + o, p, r, "f-cand s-plate data", stroke_width=1)
        for o, p in zip(oc, pc, strict=True)
    ]
    if coords is not None:
        coords.update(
            base=[(cb + o, p) for o, p in zip(ob, pb, strict=True)],
            cand=[(cc + o, p) for o, p in zip(oc, pc, strict=True)],
            ys=ys,
            px=px,
            bmed=bmed,
        )
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
) -> str:
    """Draw one thin row of run-order squares per VM: "A" is base (grey), "B" candidate."""
    out = []
    for r, (label, seq) in enumerate(rows):
        y = y0 + r * pitch
        out.append(text(x0, y + h, label, "mono f-muted"))
        for i, a in enumerate(seq):
            x = x0 + label_w + i * (cell + gap) + (i // 2) * pair_gap
            out.append(rect(x, y, cell, h, "f-base" if a == "A" else "f-cand", rx=2))
    return "".join(out)


def abba_rows(pairs: list[Pair]) -> list[tuple[str, str]]:
    return [(f"VM {s + 1}", "".join(p.order for p in pairs if p.shard == s)) for s in range(4)]


def axis_range(vals: list[float], pad: float = 0.08) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return lo - span * pad, hi + span * pad


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


# ---------------------------------------------------------------- plate and motion


class Anim:
    """Collect CSS keyframes. Every animation of a plate shares one loop length.

    An element's own attributes hold its still state (the one that
    ``prefers-reduced-motion`` shows); the keyframes move it away from that state.
    """

    def __init__(self, loop: float) -> None:
        self.loop = loop
        self.rules: list[str] = []
        self._names: dict[str, str] = {}

    def style(
        self, frames: list[tuple[float, str]], *, at: float = 0.0, ease: str = "ease-in-out"
    ) -> str:
        """Return an inline style that runs frames ((percent, declarations), ...).

        at is the second of the loop where the keyframes' 0 % falls. A negative delay
        starts every element mid-loop, so the first frame is already correct.
        """
        body = "".join(f"{p:.2f}%{{{d}}}" for p, d in frames)
        name = self._names.get(body)
        if name is None:
            name = self._names[body] = f"k{len(self._names)}"
            self.rules.append(f"@keyframes {name}{{{body}}}")
        delay = -((self.loop - at) % self.loop)
        return f"animation:{name} {self.loop:g}s {ease} {delay:.3f}s infinite"


def tr(dx: float, dy: float) -> str:
    return f"transform:translate({num(dx)}px,{num(dy)}px)"


def window(start: float, end: float, fade: float, loop: float) -> list[tuple[float, str]]:
    """Return opacity keyframes: shown from start to end seconds, fades of fade seconds."""
    p = [t / loop * 100 for t in (start, start + fade, end - fade, end)]
    out = [(0.0, "opacity:0")] if p[0] > 0 else []
    out += [(p[0], "opacity:0"), (p[1], "opacity:1"), (p[2], "opacity:1"), (p[3], "opacity:0")]
    if p[3] < 100:
        out.append((100.0, "opacity:0"))
    return out


class Plate:
    def __init__(
        self,
        title: str,
        height: float,
        desc: str,
        big: tuple[str, str] | None = None,
        loop: float = 6.0,
    ) -> None:
        self.title, self.height, self.desc, self.big = title, height, desc, big
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.extra: dict[str, tuple[str, str]] = {}  # class -> (light fill, dark fill)
        self.anim = Anim(loop)

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def fill_class(self, light: str, dark: str) -> str:
        for name, val in self.extra.items():
            if val == (light, dark):
                return name
        name = f"x{len(self.extra)}"
        self.extra[name] = (light, dark)
        return name

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
            + "".join(self.anim.rules)
            + REDUCED_CSS
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
        defs = el("defs", "".join(self.defs)) if self.defs else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(self.title)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{defs}{''.join(head)}{''.join(self.parts)}</svg>\n"
        )


def axis_ticks(
    x0: float, x1: float, ys, ticks: list[float], fmt_, *, label_x: float | None = None
) -> str:
    out = []
    for t in ticks:
        out.append(line(x0, ys(t), x1, ys(t), "s-grid"))
        lx = x0 - 7 if label_x is None else label_x
        out.append(text(lx, ys(t) + 5, fmt_(t), "mono f-muted", FS, "end"))
    return "".join(out)


def median_bar(cx: float, y: float, hw: float, tok: str) -> str:
    bar = line(cx - hw, y, cx + hw, y, "s-plate", 9, stroke_linecap="round")
    return bar + line(cx - hw, y, cx + hw, y, f"s-{tok}", 5, stroke_linecap="round")


def ci_bracket(bx: float, y_a: float, y_b: float, y_est: float, tok: str, **attrs: object) -> str:
    y_lo, y_hi = sorted((y_a, y_b))
    d = f"M{num(bx - 7)} {num(y_lo)}H{num(bx)}V{num(y_hi)}H{num(bx - 7)}"
    br = el(
        "path",
        d=d,
        cls=f"s-{tok}",
        fill="none",
        stroke_width=3,
        stroke_linecap="round",
        stroke_linejoin="round",
        **attrs,
    )
    return br + line(bx - 9, y_est, bx + 3, y_est, f"s-{tok}", 3, stroke_linecap="round", **attrs)


def panel_head(x: float, name: str, big: str, kind: str, y: float = 80) -> str:
    g, _ = glyph(kind, x + len(big) * 15.5 + 8, y + 36, 26)
    return text(x, y, name, "mono f-ink2") + text(x, y + 36, big, "f-ink bb", 28) + g


def k_plan() -> str:
    return verdict(-C90[1], -C90[0], MARGIN)


def k_track() -> str:
    return verdict(-TRACK_C90[1], -TRACK_C90[0], MARGIN)


def planning_panel(x0: float, x1: float, y0: float, y1: float, motion, coords=None) -> str:
    lo, hi = axis_range([p.base for p in PAIRS] + [p.cand for p in PAIRS])
    return dot_panel(
        x0=x0,
        x1=x1,
        y0=y0,
        y1=y1,
        base=[p.base for p in PAIRS],
        cand=[p.cand for p in PAIRS],
        lo=lo,
        hi=hi,
        ci=C90,
        est=EST,
        kind=k_plan(),
        ticks=nice_ticks(lo, hi),
        tick_fmt=lambda t: f"{t:g}",
        r=4,
        motion=motion,
        coords=coords,
    )


def tracking_panel(x0: float, x1: float, y0: float, y1: float, motion, coords=None) -> str:
    lo, hi = axis_range([p.base for p in TRACK] + [p.cand for p in TRACK])
    return dot_panel(
        x0=x0,
        x1=x1,
        y0=y0,
        y1=y1,
        base=[p.base for p in TRACK],
        cand=[p.cand for p in TRACK],
        lo=lo,
        hi=hi,
        ci=TRACK_C90,
        est=TRACK_EST,
        kind=k_track(),
        ticks=nice_ticks(lo, hi),
        tick_fmt=lambda t: f"{t:g}",
        r=4,
        motion=motion,
        coords=coords,
    )


# ---------------------------------------------------------------- A: morph to differences

# The loop of a morph, in seconds: still, move, hold, move back, still.
MORPH = (0.8, 1.7, 4.85, 5.6)


def morph_column(
    pl: Plate, coords: dict, *, xl: float, xr: float, y0: float, y1: float, r: float = 4
) -> str:
    """Draw the column of paired differences, and the dot copies that fly into it.

    The paired base and candidate dots each send a copy that meets at the pair's
    % change. The column's own axis, a faint copy of the differences, and the zero line
    stay all the time, so the column is never empty. The ±Δ band and the CI show only
    while the differences are held.
    """
    loop = pl.anim.loop
    a, b, c, d = (t / loop * 100 for t in MORPH)
    diffs = [pct(x) for x in LOG_DIFF]
    lo, hi = axis_range([*diffs, pct(C90[0]), pct(C90[1]), pct(MARGIN), pct(-MARGIN), 0.0])

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    px = xl + 44
    cx = px + (xr - px) * 0.42
    out = [axis_ticks(px, xr, ys, nice_ticks(lo, hi), signed)]
    kind = k_plan()
    mark = VERDICT[kind][0]
    band = rect(px + 2, ys(pct(MARGIN)), xr - px - 4, ys(pct(-MARGIN)) - ys(pct(MARGIN)), "")
    out.append(line(px, ys(0), xr, ys(0), "s-ink2", 1.4))
    pos = [ys(v) for v in diffs]
    off = swarm(pos, r)
    out += [
        circle(cx + o, p, r, "f-cand data", fill_opacity=0.28)
        for o, p in zip(off, pos, strict=True)
    ]
    bx = cx + max(abs(o) for o in off) + r + 16
    held = el(
        "g",
        el("g", band, cls="f-band s-bandEdge", stroke_width=1)
        + ci_bracket(bx, ys(pct(C90[0])), ys(pct(C90[1])), ys(pct(EST)), mark),
        cls="anim",
        style=pl.anim.style(
            [
                (0, "opacity:0"),
                (b, "opacity:0"),
                (b + 3, "opacity:1"),
                (c - 3, "opacity:1"),
                (c, "opacity:0"),
                (100, "opacity:0"),
            ]
        ),
    )
    out.insert(1, held)
    for arm in ("base", "cand"):
        for (sx, sy), o, p in zip(coords[arm], off, pos, strict=True):
            tx, ty = cx + o, p
            away, home = tr(sx - tx, sy - ty), tr(0, 0)
            # the base copy fades as it lands, so one dot remains per pair
            ops = (0, 1, 1, 1, 1, 0) if arm == "cand" else (0, 1, 0, 0, 1, 0)
            frames = [
                (0, f"{away};opacity:0"),
                (a - 0.3, f"{away};opacity:{ops[0]}"),
                (a, f"{away};opacity:{ops[1]}"),
                (b, f"{home};opacity:{ops[2]}"),
                (c, f"{home};opacity:{ops[3]}"),
                (d, f"{away};opacity:{ops[4]}"),
                (d + 0.3, f"{away};opacity:{ops[5]}"),
                (100, f"{away};opacity:0"),
            ]
            out.append(
                circle(
                    tx,
                    ty,
                    r,
                    f"f-{arm} s-plate anim {'rm-off' if arm == 'base' else ''}".strip(),
                    stroke_width=1,
                    style=pl.anim.style(frames),
                )
            )
    out.append(text(px, y1 + 26, "per-pair change · %", "f-ink2", FS))
    out.append(text(px, y1 + 45, f"n={len(diffs)} pairs", "mono f-muted", FS))
    label = [
        (0, "opacity:0"),
        (a - 1, "opacity:0"),
        (a, "opacity:1"),
        (b, "opacity:1"),
        (b + 2, "opacity:0"),
        (c - 1, "opacity:0"),
        (c, "opacity:1"),
        (d, "opacity:1"),
        (d + 2, "opacity:0"),
        (100, "opacity:0"),
    ]
    out.append(
        text(
            xl,
            y0 - 12,
            "pairs → differences",
            "f-ink bb anim rm-off",
            FS + 1,
            style=pl.anim.style(label, ease="linear"),
        )
    )
    return "".join(out)


def plate_a() -> Plate:
    desc = (
        f"planning_time: 20 paired runs, base and candidate columns in seconds. Each pair "
        f"moves into one dot at its % change; then the ±5 % band and the 90 % CI "
        f"{fmt(pct(C90[0]))} to {fmt(pct(C90[1]))} % show on that column. Loop 6 s."
    )
    pl = Plate(
        f"Planning is {abs(pct(EST)):.0f} % faster",
        470,
        desc,
        (k_plan(), f"{fmt(pct(EST))} %"),
    )
    coords: dict = {}
    pl.add(
        text(20, 80, "planning_time · s", "mono f-ink2"),
        planning_panel(20, 450, 100, 380, (), coords),
        morph_column(pl, coords, xl=490, xr=780, y0=100, y1=380, r=4),
    )
    return pl


# ---------------------------------------------------------------- B: blink comparison

BLINK = 2.0  # one swap a second; each crossfade 150 ms


def blink_pair(pl: Plate, base_svg: str, cand_svg: str) -> str:
    """Show base_svg and cand_svg in the same place, swapping once a second."""
    loop = pl.anim.loop
    fa: list[tuple[float, str]] = []
    for j in range(round(loop / BLINK)):
        t = j * BLINK
        fa += [
            (t / loop * 100, "opacity:1"),
            ((t + BLINK / 2 - 0.15) / loop * 100, "opacity:1"),
            ((t + BLINK / 2) / loop * 100, "opacity:0"),
            ((t + BLINK - 0.15) / loop * 100, "opacity:0"),
        ]
    fa.append((100, "opacity:1"))
    fb = [(p, "opacity:0" if "1" in s else "opacity:1") for p, s in fa]
    return el("g", base_svg, cls="anim rm-off", style=pl.anim.style(fa)) + el(
        "g", cand_svg, cls="anim", style=pl.anim.style(fb)
    )


def blink_label(pl: Plate, x: float, y: float, size: float = FS) -> str:
    def lab(tok: str, name: str) -> str:
        return rect(x, y - size * 0.75, size * 0.8, size * 0.8, f"f-{tok}", rx=2) + text(
            x + size * 1.15, y, name, "f-ink b", size
        )

    return blink_pair(pl, lab("base", "base"), lab("cand", "candidate"))


def one_column(values: list[float], cx: float, ys, r: float, tok: str, hw_max: float = 40) -> str:
    pos = [ys(v) for v in values]
    off = swarm(pos, r)
    out = [
        circle(cx + o, p, r, f"f-{tok} s-plate data", stroke_width=1)
        for o, p in zip(off, pos, strict=True)
    ]
    hw = min(max(abs(o) for o in off) + r + 5, hw_max)
    out.append(median_bar(cx, ys(quant(values, 0.5)), hw, tok))
    return "".join(out)


def blink_column(
    pl: Plate, pairs: list[Pair], *, x0: float, x1: float, y0: float, y1: float, r: float = 4.5
) -> str:
    vals = [p.base for p in pairs] + [p.cand for p in pairs]
    lo, hi = axis_range(vals)

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    px = x0 + 48
    cx = (px + x1) / 2
    bmed = quant([p.base for p in pairs], 0.5)
    top, bot = ys(bmed * math.exp(MARGIN)), ys(bmed * math.exp(-MARGIN))
    return (
        axis_ticks(px, x1, ys, nice_ticks(lo, hi), lambda t: f"{t:g}")
        + rect(px + 2, top, x1 - px - 4, bot - top, "f-band s-bandEdge", stroke_width=1)
        + blink_pair(
            pl,
            one_column([p.base for p in pairs], cx, ys, r, "base"),
            one_column([p.cand for p in pairs], cx, ys, r, "cand"),
        )
    )


HEAT_SPEED, HEAT_LOAD = [0.4, 0.8, 1.2, 1.6], [0.5, 1, 2, 4, 6]


def heat_cells() -> list[tuple[int, int, float, float]]:
    """Return (row, col, base s, candidate s): the cycle time of each load x speed cell.

    The % change per cell is the G7 formula of #1188; the base cycle time is made up.
    """
    out = []
    for r, m in enumerate(HEAT_LOAD):
        for k, v in enumerate(HEAT_SPEED):
            p = -(m * v * 2.2) + 1.5
            base = 1.6 + 0.32 * m + 1.1 / v
            out.append((r, k, base, base * (1 + p / 100)))
    return out


def heat_grid(pl: Plate, arm: int, *, x0: float, y0: float, cw: float, ch: float) -> str:
    """Draw the raw cycle times of one arm (0 base, 1 candidate) on one shared scale."""
    cells = heat_cells()
    vals = [c[2] for c in cells] + [c[3] for c in cells]
    lo, hi = min(vals), max(vals)
    out = []
    for r, k, *v in cells:
        val = v[arm]
        share = round((0.12 + 0.83 * (val - lo) / (hi - lo)) * 40) / 40
        fill = pl.fill_class(
            mix(LIGHT["ink2"], LIGHT["chip"], share), mix(DARK["ink2"], DARK["chip"], share)
        )
        deep = share > 0.55
        ink = pl.fill_class(
            LIGHT["white"] if deep else LIGHT["ink"], DARK["plate"] if deep else DARK["ink"]
        )
        x, y = x0 + k * cw, y0 + r * ch
        out.append(rect(x + 1, y + 1, cw - 2, ch - 2, f"{fill} data", rx=3))
        out.append(text(x + cw / 2, y + ch / 2 + 5, f"{val:.2f}", f"mono {ink}", FS, "middle"))
    return "".join(out)


def blink_heat(pl: Plate, *, x0: float, y0: float, cw: float, ch: float) -> str:
    kw = {"x0": x0, "y0": y0, "cw": cw, "ch": ch}
    pair = blink_pair(pl, heat_grid(pl, 0, **kw), heat_grid(pl, 1, **kw))
    return pair + _heat_labels(x0, y0, cw, ch)


def _heat_labels(x0: float, y0: float, cw: float, ch: float) -> str:
    out = [
        text(x0 - 8, y0 + r * ch + ch / 2 + 5, f"{m} kg", "mono f-muted", FS, "end")
        for r, m in enumerate(HEAT_LOAD)
    ]
    out += [
        text(
            x0 + k * cw + cw / 2,
            y0 + len(HEAT_LOAD) * ch + 22,
            f"{v:g}",
            "mono f-muted",
            FS,
            "middle",
        )
        for k, v in enumerate(HEAT_SPEED)
    ]
    return "".join(out)


def plate_b() -> Plate:
    cells = heat_cells()
    best = min(cells, key=lambda c: c[3] / c[2])
    kp, kt = k_plan(), k_track()
    title = "Planning shifts; tracking does not" if kt in {"equiv", "small"} else "Both shift"
    desc = (
        f"Base and candidate swap in place once a second. planning_time moves "
        f"{fmt(pct(EST))} % ({kp}); the cycle_time grid (illustrative values) drops most "
        f"at {HEAT_LOAD[best[0]]} kg and {HEAT_SPEED[best[1]]} m/s, "
        f"{fmt((best[3] / best[2] - 1) * 100, 0)} %; tracking_error does not move "
        f"({fmt(pct(TRACK_EST))} %). Loop 2 s."
    )
    pl = Plate(title, 500, desc, loop=BLINK)
    y0, y1 = 120, 400
    pl.add(
        text(20, 80, "planning_time · s", "mono f-ink2"),
        blink_label(pl, 20, 104),
        blink_column(pl, PAIRS, x0=20, x1=230, y0=y0, y1=y1),
        text(300, 80, "cycle_time · s", "mono f-ink2"),
        blink_label(pl, 300, 104),
        blink_heat(pl, x0=340, y0=y0, cw=58, ch=56),
        text(600, 80, "tracking_error · mm", "mono f-ink2"),
        blink_label(pl, 600, 104),
        blink_column(pl, TRACK, x0=580, x1=780, y0=y0, y1=y1),
        text(340, 470, "speed · m/s", "f-muted", FS),
        text(20, 470, "n=20 per arm", "mono f-muted", FS),
    )
    return pl


# ---------------------------------------------------------------- C: where a metric comes from

TRACE_T = 8.0
TRACE_N = 241
C_RUNS = [(0, "base"), (0, "cand"), (13, "base"), (13, "cand")]  # (pair index, arm)


def synth_trace(rng: XorShift, rms: float) -> list[float]:
    """Return |tracking error| over 8 s for one run, scaled so its RMS equals rms."""
    ph = rng.rnd() * 6.3
    raw = []
    for i in range(TRACE_N):
        t = i * TRACE_T / (TRACE_N - 1)
        env = 0.25 + sum(math.exp(-(((t - c) / 0.7) ** 2)) for c in (1.6, 4.1, 6.5))
        raw.append(env * math.sin(2 * math.pi * 1.3 * t + ph) + 0.05 * rng.norm())
    k = rms / math.sqrt(mean([x * x for x in raw]))
    return [abs(x) * k for x in raw]


def plate_c() -> Plate:
    kind = k_track()
    rng = XorShift(808)
    runs = []
    for pi, arm in C_RUNS:
        val = TRACK[pi].base if arm == "base" else TRACK[pi].cand
        runs.append((pi, arm, val, synth_trace(rng, val)))
    desc = (
        "Each tracking_error value is the RMS of one run's error trace (synthetic traces, "
        "scaled to the run's value). Four runs play in turn: the RMS line is drawn, then the "
        f"value lands as its dot. Change {fmt(pct(TRACK_EST))} %. Loop 6 s."
    )
    title = "Tracking error is unchanged" if kind in {"equiv", "small"} else "Tracking changed"
    pl = Plate(title, 470, desc, (kind, f"{fmt(pct(TRACK_EST))} %"))
    loop = pl.anim.loop
    slot = loop / len(runs)
    x0, x1, y0, y1 = 70, 440, 110, 380
    top = max(max(tr_) for *_, tr_ in runs) * 1.05

    def tx(t: float) -> float:
        return x0 + t / TRACE_T * (x1 - x0)

    def ty(v: float) -> float:
        return y1 - v / top * (y1 - y0)

    pl.add(axis_ticks(x0, x1, ty, nice_ticks(0, top), lambda t: f"{t:g}"))
    for t in range(0, 9, 2):
        pl.add(text(tx(t), y1 + 22, f"{t}", "mono f-muted", FS, "middle"))
    pl.add(
        text(x1, y1 + 42, "time · s", "f-muted", FS, "end"),
        text(20, 80, "|error| · mm, one run", "mono f-ink2"),
        text(x0, y1 + 42, "synthetic trace", "f-muted", FS),
    )
    coords: dict = {}
    pl.add(
        text(500, 80, "tracking_error · mm", "mono f-ink2"),
        tracking_panel(480, 780, y0, y1, (), coords),
    )
    for j, (pi, arm, val, trace) in enumerate(runs):
        at = j * slot
        win = window(0, slot, 0.15, loop)
        rm = "rm-on" if j == 0 else "rm-off"
        d = "M" + "L".join(
            f"{num(tx(i * TRACE_T / (TRACE_N - 1)))} {num(ty(v))}" for i, v in enumerate(trace)
        )
        tok = "base" if arm == "base" else "cand"
        name = "base" if arm == "base" else "candidate"
        pl.add(
            el(
                "g",
                el("path", d=d, cls=f"s-{tok}", fill="none", stroke_width=1.6)
                + text(x0, y0 - 8, f"pair {pi + 1} · {name}", "f-ink b", FS),
                cls=f"data anim {rm}",
                style=pl.anim.style(win, at=at),
            )
        )
        yr = ty(val)
        span = x1 - x0
        p1, p2 = 0.55 / loop * 100, 0.95 / loop * 100
        p3, p4 = (slot - 0.15) / loop * 100, slot / loop * 100
        draw = [
            (0, f"stroke-dashoffset:{num(span)};opacity:1"),
            (0.15 / loop * 100, f"stroke-dashoffset:{num(span)};opacity:1"),
            (p1, "stroke-dashoffset:0;opacity:1"),
            (p3, "stroke-dashoffset:0;opacity:1"),
            (p4, "stroke-dashoffset:0;opacity:0"),
            (100, f"stroke-dashoffset:{num(span)};opacity:0"),
        ]
        pl.add(
            line(
                x0,
                yr,
                x1,
                yr,
                "s-ink anim " + rm,
                2,
                stroke_dasharray=f"{num(span)} {num(span)}",
                style=pl.anim.style(draw, at=at),
            ),
            text(
                x1 - 4,
                yr - 8,
                f"rms {val:.1f}",
                "mono f-ink bb anim " + rm,
                FS,
                "end",
                style=pl.anim.style(window(0.5, slot, 0.1, loop), at=at),
            ),
        )
        gx, gy = coords[tok][pi]
        away = tr(x1 - gx, yr - gy)
        fly = [
            (0, f"{away};opacity:0"),
            (p1, f"{away};opacity:0"),
            (p1 + 0.5, f"{away};opacity:1"),
            (p2, f"{tr(0, 0)};opacity:1"),
            (p3, f"{tr(0, 0)};opacity:1"),
            (p4, f"{tr(0, 0)};opacity:0"),
            (100, f"{away};opacity:0"),
        ]
        pl.add(
            circle(
                gx,
                gy,
                4.5,
                f"f-{tok} s-plate anim {rm}",
                stroke_width=1,
                style=pl.anim.style(fly, at=at),
            ),
            circle(
                gx,
                gy,
                8,
                f"s-ink anim {rm}",
                fill="none",
                stroke_width=2,
                style=pl.anim.style(window(p2 / 100 * loop, slot, 0.1, loop), at=at),
            ),
        )
    return pl


# ---------------------------------------------------------------- D: trajectory replay

TRAJ_T, TRAJ_N = 4.0, 81  # 4 s of motion at 20 Hz, then 1 s hold
GOAL = (240.0, 120.0)
SETTLE_MM = 5.0


def _step(zeta: float, wn: float, t: float) -> float:
    """Return the unit step response of a second-order system."""
    if zeta < 1:
        wd = wn * math.sqrt(1 - zeta * zeta)
        return 1 - math.exp(-zeta * wn * t) * (
            math.cos(wd * t) + zeta / math.sqrt(1 - zeta * zeta) * math.sin(wd * t)
        )
    return 1 - math.exp(-wn * t) * (1 + wn * t)


def synth_path(zeta: float, rng: XorShift) -> list[tuple[float, float]]:
    """Return a 2-D end-effector path from (0, 0) to GOAL.

    x and y follow second-order steps with different natural frequencies, so the path
    curves; a small zeta makes it overshoot and circle the goal.
    """
    gx, gy = GOAL
    out = []
    for i in range(TRAJ_N):
        t = i * TRAJ_T / (TRAJ_N - 1)
        n = 0.4 * rng.norm() if 0 < i < TRAJ_N - 1 else 0.0
        out.append((gx * _step(zeta, 4.6, t) + n, gy * _step(zeta, 2.9, t) + n))
    return out


def overshoot(path: list[tuple[float, float]]) -> float:
    """Return how far the path goes past the goal on either axis, in mm."""
    gx, gy = GOAL
    return max(0.0, *(max(x - gx, y - gy) for x, y in path))


def plate_d() -> Plate:
    rng = XorShift(4242)
    paths = {"base": synth_path(0.3, rng), "cand": synth_path(1.0, rng)}
    os_b, os_c = overshoot(paths["base"]), overshoot(paths["cand"])
    kind = "improved" if os_c < os_b - SETTLE_MM else "equiv"
    title = "Candidate removes the overshoot" if os_c < 1 else "Candidate cuts the overshoot"
    desc = (
        f"Synthetic end-effector paths to one goal, base and candidate. A time cursor replays "
        f"both in sync. Overshoot past the goal: base {os_b:.0f} mm, candidate {os_c:.0f} mm. "
        f"Loop 5 s."
    )
    pl = Plate(title, 480, desc, (kind, f"{fmt(os_c - os_b, 0)} mm"), loop=5.0)
    loop = pl.anim.loop
    moving = TRAJ_T / loop * 100
    xs = [p[0] for ps in paths.values() for p in ps] + [0, GOAL[0]]
    ys_ = [p[1] for ps in paths.values() for p in ps] + [0, GOAL[1]]
    bx0, bx1, by0, by1 = 70, 470, 110, 400
    sx, sy = axis_range(xs, 0.06), axis_range(ys_, 0.1)
    k = min((bx1 - bx0) / (sx[1] - sx[0]), (by1 - by0) / (sy[1] - sy[0]))

    def px(p: tuple[float, float]) -> tuple[float, float]:
        return bx0 + (p[0] - sx[0]) * k, by1 - (p[1] - sy[0]) * k

    for t in nice_ticks(*sx):
        x = bx0 + (t - sx[0]) * k
        if x <= bx1:
            pl.add(
                line(x, by0, x, by1, "s-grid"),
                text(x, by1 + 22, f"{t:g}", "mono f-muted", FS, "middle"),
            )
    for t in nice_ticks(*sy):
        y = by1 - (t - sy[0]) * k
        if y >= by0:
            pl.add(
                line(bx0, y, bx1, y, "s-grid"),
                text(bx0 - 7, y + 5, f"{t:g}", "mono f-muted", FS, "end"),
            )
    gx, gy = px(GOAL)
    s0 = px((0, 0))
    pl.add(
        text(20, 80, "end-effector path · mm", "mono f-ink2"),
        text(bx1, by1 + 42, "x · mm  (synthetic paths)", "f-muted", FS, "end"),
        circle(gx, gy, SETTLE_MM * k, "f-band s-bandEdge", stroke_width=1),
        line(gx - 7, gy, gx + 7, gy, "s-ink", 1.5),
        line(gx, gy - 7, gx, gy + 7, "s-ink", 1.5),
        text(gx + 12, gy + 22, "goal", "f-ink2", FS),
        circle(*s0, 4, "f-ink2"),
        text(s0[0] + 8, s0[1] + 18, "start", "f-ink2", FS),
    )
    # distance to the goal over time, with the same cursor
    rx0, rx1, ry0, ry1 = 560, 780, 110, 400
    dist = {a: [math.hypot(x - GOAL[0], y - GOAL[1]) for x, y in ps] for a, ps in paths.items()}
    dmax = max(max(v) for v in dist.values()) * 1.05

    def rxy(i: int, v: float) -> tuple[float, float]:
        return rx0 + i / (TRAJ_N - 1) * (rx1 - rx0), ry1 - v / dmax * (ry1 - ry0)

    pl.add(
        axis_ticks(rx0, rx1, lambda v: rxy(0, v)[1], nice_ticks(0, dmax), lambda t: f"{t:g}"),
        rect(rx0, rxy(0, SETTLE_MM)[1], rx1 - rx0, ry1 - rxy(0, SETTLE_MM)[1], "f-band"),
        text(520, 80, "distance to goal · mm", "mono f-ink2"),
        text(rx1, ry1 + 42, "time · s", "f-muted", FS, "end"),
    )
    for t in range(5):
        pl.add(text(rxy(t * 20, 0)[0], ry1 + 22, f"{t}", "mono f-muted", FS, "middle"))
    for arm, ps in paths.items():
        pts = [px(p) for p in ps]
        d = "M" + "L".join(f"{num(x)} {num(y)}" for x, y in pts)
        cum = [0.0]
        for (xa, ya), (xb, yb) in itertools.pairwise(pts):
            cum.append(cum[-1] + math.hypot(xb - xa, yb - ya))
        total = cum[-1]
        pl.add(el("path", d=d, cls=f"s-{arm} data", fill="none", stroke_width=2, opacity=0.3))
        trail = [
            (i / (TRAJ_N - 1) * moving, f"stroke-dashoffset:{num(total - c)}")
            for i, c in enumerate(cum)
        ]
        trail.append((100, "stroke-dashoffset:0"))
        pl.add(
            el(
                "path",
                d=d,
                cls=f"s-{arm} anim",
                fill="none",
                stroke_width=3,
                stroke_linecap="round",
                stroke_dasharray=f"{num(total + 1)} {num(total + 1)}",
                style=pl.anim.style(trail, ease="linear"),
            )
        )
        ex, ey = pts[-1]
        mv = [(i / (TRAJ_N - 1) * moving, tr(x - ex, y - ey)) for i, (x, y) in enumerate(pts)]
        mv.append((100, tr(0, 0)))
        pl.add(
            circle(
                ex,
                ey,
                6,
                f"f-{arm} s-plate anim",
                stroke_width=1.5,
                style=pl.anim.style(mv, ease="linear"),
            )
        )
        dd = "M" + "L".join(
            f"{num(rxy(i, v)[0])} {num(rxy(i, v)[1])}" for i, v in enumerate(dist[arm])
        )
        pl.add(el("path", d=dd, cls=f"s-{arm} data", fill="none", stroke_width=2.2))
        lx, ly = rxy(TRAJ_N - 1, dist[arm][-1])
        dm = [
            (i / (TRAJ_N - 1) * moving, tr(rxy(i, v)[0] - lx, rxy(i, v)[1] - ly))
            for i, v in enumerate(dist[arm])
        ]
        dm.append((100, tr(0, 0)))
        pl.add(
            circle(
                lx,
                ly,
                5,
                f"f-{arm} s-plate anim",
                stroke_width=1.5,
                style=pl.anim.style(dm, ease="linear"),
            )
        )
    pl.add(
        line(
            rx1,
            ry0,
            rx1,
            ry1,
            "s-ink anim",
            1.5,
            style=pl.anim.style(
                [(0, tr(rx0 - rx1, 0)), (moving, tr(0, 0)), (100, tr(0, 0))], ease="linear"
            ),
        )
    )
    steps = 21
    for j in range(steps):
        t0 = j * 0.2
        t1 = loop if j == steps - 1 else t0 + 0.2
        p0, p1 = t0 / loop * 100, t1 / loop * 100
        fr = [(0, "opacity:0")] if p0 > 0 else []
        fr += [(p0, "opacity:1"), (p1 - 0.01, "opacity:1"), (p1, "opacity:0")]
        if p1 < 100:
            fr.append((100, "opacity:0"))
        pl.add(
            text(
                bx1,
                by0 - 8,
                f"t = {t0:.1f} s",
                f"mono f-ink bb anim {'rm-on' if j == steps - 1 else 'rm-off'}",
                FS + 1,
                "end",
                style=pl.anim.style(fr, ease="step-end"),
            )
        )
    pl.add(
        rect(bx0, 452, 13, 13, "f-base", rx=2),
        text(bx0 + 19, 464, "base", "f-ink2"),
        rect(bx0 + 70, 452, 13, 13, "f-cand", rx=2),
        text(bx0 + 89, 464, "candidate", "f-ink2"),
    )
    return pl


# ---------------------------------------------------------------- E: change of scale

SCALE = (2.0, 3.0, 5.0, 6.0)  # hold seconds, rescale, hold log ratio, rescale back


def plate_e() -> Plate:
    desc = (
        "planning_time dots keep their order while the y axis changes from seconds to the "
        "% change from the base median (a log ratio). On the log-ratio axis the ±5 % band is "
        f"the same on both sides and the CI reads in %: {fmt(pct(C90[0]))} to "
        f"{fmt(pct(C90[1]))} %. Loop 6 s."
    )
    pl = Plate(
        f"Planning is {abs(pct(EST)):.0f} % faster", 480, desc, (k_plan(), f"{fmt(pct(EST))} %")
    )
    loop = pl.anim.loop
    a, b, c, d = (t / loop * 100 for t in SCALE)
    base, cand = [p.base for p in PAIRS], [p.cand for p in PAIRS]
    bmed = quant(base, 0.5)
    y0, y1 = 110, 400
    lin = axis_range(base + cand)
    lr = [100 * math.log(v / bmed) for v in base + cand]
    lg = axis_range([*lr, 100 * MARGIN])

    def y_lin(v: float) -> float:
        return y1 - (v - lin[0]) / (lin[1] - lin[0]) * (y1 - y0)

    def y_log(v: float) -> float:
        return y1 - (100 * math.log(v / bmed) - lg[0]) / (lg[1] - lg[0]) * (y1 - y0)

    def frames(lin_decl: str, log_decl: str) -> list[tuple[float, str]]:
        return [
            (0, lin_decl),
            (a, lin_decl),
            (b, log_decl),
            (c, log_decl),
            (d, lin_decl),
            (100, lin_decl),
        ]

    px0, px1 = 120, 600
    # seconds ticks: shown in the seconds state
    for t in nice_ticks(*lin, 5):
        g = line(px0, y_log(t), px1, y_log(t), "s-grid") + text(
            px0 - 8, y_log(t) + 5, f"{t:g} s", "mono f-muted", FS, "end"
        )
        dy = y_lin(t) - y_log(t)
        pl.add(
            el(
                "g",
                g,
                cls="anim rm-off",
                style=pl.anim.style(frames(f"{tr(0, dy)};opacity:1", f"{tr(0, 0)};opacity:0")),
            )
        )
    # % ticks: shown in the log-ratio state
    lo_p, hi_p = pct(lg[0] / 100), pct(lg[1] / 100)
    for t in nice_ticks(lo_p, hi_p, 6):
        v = bmed * (1 + t / 100)
        g = line(
            px0, y_log(v), px1, y_log(v), "s-ink2" if t == 0 else "s-grid", 1.4 if t == 0 else 1
        ) + text(px0 - 8, y_log(v) + 5, f"{signed(t)} %", "mono f-muted", FS, "end")
        pl.add(
            el(
                "g",
                g,
                cls="anim",
                style=pl.anim.style(
                    frames(f"{tr(0, y_lin(v) - y_log(v))};opacity:0", f"{tr(0, 0)};opacity:1")
                ),
            )
        )

    def squash(ya_log: float, yb_log: float, ya_lin: float, yb_lin: float) -> str:
        """Return the transform that maps the log-state span to the seconds-state span."""
        k = (yb_lin - ya_lin) / (yb_log - ya_log)
        return f"transform:translate(0px,{num(ya_lin - k * ya_log)}px) scale(1,{k:.4f})"

    hi_b, lo_b = bmed * math.exp(MARGIN), bmed * math.exp(-MARGIN)
    band = rect(
        px0 + 2,
        y_log(hi_b),
        px1 - px0 - 4,
        y_log(lo_b) - y_log(hi_b),
        "f-band s-bandEdge",
        stroke_width=1,
        vector_effect="non-scaling-stroke",
    )
    pl.add(
        el(
            "g",
            band,
            cls="anim",
            style=pl.anim.style(
                frames(
                    squash(y_log(hi_b), y_log(lo_b), y_lin(hi_b), y_lin(lo_b)),
                    "transform:translate(0px,0px) scale(1,1)",
                )
            ),
        )
    )
    cb, cc = 270, 450
    r = 4.5
    for vals, cx, tok in ((base, cb, "base"), (cand, cc, "cand")):
        o_lin = swarm([y_lin(v) for v in vals], r)
        o_log = swarm([y_log(v) for v in vals], r)
        for v, ol, og in zip(vals, o_lin, o_log, strict=True):
            pl.add(
                circle(
                    cx + og,
                    y_log(v),
                    r,
                    f"f-{tok} s-plate data anim",
                    stroke_width=1,
                    style=pl.anim.style(frames(tr(ol - og, y_lin(v) - y_log(v)), tr(0, 0))),
                )
            )
        m = quant(vals, 0.5)
        hw = min(max(abs(o) for o in o_log) + r + 5, 60)
        pl.add(
            el(
                "g",
                median_bar(cx, y_log(m), hw, tok),
                cls="anim",
                style=pl.anim.style(frames(tr(0, y_lin(m) - y_log(m)), tr(0, 0))),
            ),
            text(cx, y1 + 26, "base" if tok == "base" else "candidate", "f-ink2", FS, "middle"),
            text(cx, y1 + 45, f"n={len(vals)}", "mono f-muted", FS, "middle"),
        )
    mark = VERDICT[k_plan()][0]
    bx = 560
    v_lo, v_hi, v_e = (bmed * math.exp(x) for x in (*C90, EST))
    pl.add(
        el(
            "g",
            ci_bracket(
                bx, y_log(v_lo), y_log(v_hi), y_log(v_e), mark, vector_effect="non-scaling-stroke"
            ),
            cls="anim",
            style=pl.anim.style(
                frames(
                    squash(y_log(v_lo), y_log(v_hi), y_lin(v_lo), y_lin(v_hi)),
                    "transform:translate(0px,0px) scale(1,1)",
                )
            ),
        )
    )
    # axis names swap with the axis
    sw = [
        (0, "opacity:1"),
        (a, "opacity:1"),
        (a + 3, "opacity:0"),
        (c, "opacity:0"),
        (c + 3, "opacity:1"),
        (100, "opacity:1"),
    ]
    sw2 = [(p, "opacity:0" if "1" in s else "opacity:1") for p, s in sw]
    pl.add(
        text(20, 80, "planning_time · s", "mono f-ink2 anim rm-off", style=pl.anim.style(sw)),
        text(
            20,
            80,
            "change from base median · % (log ratio)",
            "mono f-ink2 anim",
            style=pl.anim.style(sw2),
        ),
    )
    lab = [
        (0, "opacity:0"),
        (a - 1, "opacity:0"),
        (a, "opacity:1"),
        (b, "opacity:1"),
        (b + 1, "opacity:0"),
        (c - 1, "opacity:0"),
        (c, "opacity:1"),
        (100, "opacity:1"),
    ]
    pl.add(
        text(
            640,
            250,
            "rescaling…",
            "f-ink bb anim rm-off",
            FS + 1,
            style=pl.anim.style(lab, ease="linear"),
        )
    )
    return pl


# ---------------------------------------------------------------- F: the PR in its history

HIST_N = 30


def history() -> list[float]:
    """Return the planning_time median of each of the last 30 commits on main (synthetic)."""
    rng = XorShift(1307)
    bmed = quant([p.base for p in PAIRS], 0.5)
    return [bmed * math.exp(0.028 * rng.norm()) for _ in range(HIST_N)]


def history_strip(*, x0: float, x1: float, y0: float, y1: float) -> str:
    hist = history()
    bmed = quant([p.base for p in PAIRS], 0.5)
    cmed = quant([p.cand for p in PAIRS], 0.5)
    logs = [math.log(v) for v in hist]
    mid, s = mean(logs), sd(logs)
    band = (math.exp(mid - 2 * s), math.exp(mid + 2 * s))
    lo, hi = axis_range([*hist, bmed, cmed, *band], 0.12)

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    px = x0 + 48
    step = (x1 - px - 60) / (HIST_N + 2)

    def xs(i: float) -> float:
        return px + 10 + i * step

    out = [axis_ticks(px, x1, ys, nice_ticks(lo, hi, 3), lambda t: f"{t:g}")]
    out.append(
        rect(
            px + 2,
            ys(band[1]),
            x1 - px - 4,
            ys(band[0]) - ys(band[1]),
            "f-band s-bandEdge",
            stroke_width=1,
        )
    )
    pts = [(xs(i), ys(v)) for i, v in enumerate(hist)]
    out.append(
        el(
            "path",
            d="M" + "L".join(f"{num(x)} {num(y)}" for x, y in pts),
            cls="s-base data",
            fill="none",
            stroke_width=1.5,
        )
    )
    out += [circle(x, y, 3, "f-base data") for x, y in pts]
    xb, xc = xs(HIST_N + 0.3), xs(HIST_N + 1.3)
    mark = VERDICT[k_plan()][0]
    out.append(line(xb, ys(bmed), xc, ys(cmed), f"s-{mark} flow", 3, stroke_linecap="round"))
    out += [
        circle(xb, ys(bmed), 5, "f-base s-plate data", stroke_width=1.5),
        circle(xc, ys(cmed), 5.5, "f-cand s-plate data", stroke_width=1.5),
    ]
    vl, vh = (bmed * math.exp(x) for x in C90)
    out.append(ci_bracket(xc + 16, ys(vl), ys(vh), ys(bmed * math.exp(EST)), mark))
    for i, lab in (
        (0, f"−{HIST_N}"),
        (HIST_N // 3, f"−{HIST_N * 2 // 3}"),
        (HIST_N * 2 // 3, f"−{HIST_N // 3}"),
    ):
        out.append(text(xs(i), y1 + 22, lab, "mono f-muted", FS, "middle"))
    out.append(text((xb + xc) / 2, y1 + 22, "this PR", "f-ink b", FS, "middle"))
    out.append(text(px, y1 + 42, "commits on main (synthetic history)", "f-muted", FS))
    return "".join(out)


def plate_f() -> Plate:
    hist = history()
    bmed = quant([p.base for p in PAIRS], 0.5)
    cmed = quant([p.cand for p in PAIRS], 0.5)
    steps = [abs(math.log(b / a)) for a, b in itertools.pairwise([*hist, bmed])]
    pr_step = abs(math.log(cmed / bmed))
    largest = pr_step > max(steps)
    title = f"Largest change in {HIST_N} commits" if largest else "A change within the noise"
    desc = (
        f"planning_time median of the last {HIST_N} commits on main (synthetic), its ±2 SD "
        f"commit-to-commit band, and this PR's base to candidate step "
        f"({fmt(pct(EST))} %). The largest earlier step is {max(steps) * 100:.1f} % (log). "
        f"Only the dashes on the PR's step move. Loop 3 s."
    )
    pl = Plate(title, 360, desc, (k_plan(), f"{fmt(pct(EST))} %"), loop=3.0)
    pl.add(
        text(20, 80, "planning_time · s, median per commit", "mono f-ink2"),
        history_strip(x0=20, x1=780, y0=100, y1=290),
    )
    return pl


# ---------------------------------------------------------------- G and H: combinations


def task_strip(x0: float, y0: float) -> str:
    """Draw task_success as two rows of run squares; a cross marks each failed run."""
    out = []
    size, gap = 15, 4
    for row, (tok, name, k) in enumerate(
        (("base", "base", TS_BASE), ("cand", "candidate", TS_CAND))
    ):
        y = y0 + row * (size + 10)
        out.append(text(x0, y + 13, name, "f-ink2", FS))
        for i in range(TS_N):
            x = x0 + 86 + i * (size + gap)
            if i >= k:
                out += [
                    rect(x, y, size, size, "f-plate s-worse", rx=3, stroke_width=2),
                    el(
                        "path",
                        d=f"M{num(x + 4)} {num(y + 4)}l7 7m0 -7l-7 7",
                        cls="s-worse",
                        stroke_width=2,
                    ),
                ]
            else:
                out.append(rect(x, y, size, size, f"f-{tok} data", rx=3))
        out.append(
            text(x0 + 86 + TS_N * (size + gap) + 4, y + 13, f"{k}/{TS_N}", "mono f-muted", FS)
        )
    return "".join(out)


def scorecard(pl: Plate, *, morph: bool, motion: tuple[str, ...], y: float = 60) -> float:
    """Draw the three-metric scorecard; return the y below it."""
    y0, y1 = y + 80, y + 300
    coords: dict = {}
    if morph:
        pl.add(
            panel_head(20, "planning_time · s", f"{fmt(pct(EST))} %", k_plan(), y + 20),
            planning_panel(20, 300, y0, y1, motion, coords),
            morph_column(pl, coords, xl=300, xr=470, y0=y0, y1=y1, r=3.6),
        )
    else:
        pl.add(
            panel_head(20, "planning_time · s", f"{fmt(pct(EST))} %", k_plan(), y + 20),
            planning_panel(20, 440, y0, y1, motion),
        )
    pl.add(
        panel_head(500, "tracking_error · mm", f"{fmt(pct(TRACK_EST))} %", k_track(), y + 20),
        tracking_panel(500, 780, y0, y1, motion),
    )
    ty = y1 + 70
    g, _ = glyph(TS_KIND, 20 + len("task_success") * 9.4 + 14 + len(TS_TXT) * 11 + 10, ty, 20)
    pl.add(
        text(20, ty, "task_success", "mono f-ink2"),
        text(20 + len("task_success") * 9.4 + 14, ty, TS_TXT, "f-ink bb", 20),
        g,
        task_strip(20, ty + 14),
        text(530, ty, "run order →", "f-muted"),
        run_rows(530, ty + 10, abba_rows(PAIRS), cell=12, h=12, gap=2, pitch=19, label_w=50),
    )
    return ty + 90


def plate_g() -> Plate:
    desc = (
        "The scorecard of #1188 with its dash flow (pair lines and the median connector "
        "flow in the direction of change) and, on planning_time only, the morph of A: the "
        "pairs move into one column of per-pair % change and back. Loop 6 s."
    )
    pl = Plate(f"Planning is {abs(pct(EST)):.0f} % faster", 520, desc)
    scorecard(pl, morph=True, motion=("connector", "pairs"))
    return pl


def plate_h() -> Plate:
    desc = (
        "The still scorecard; under it the planning_time history of the last 30 commits "
        "(synthetic) with dash flow on this PR's step; under that the cycle_time grid "
        "(illustrative values) that blinks between base and candidate. Loop 6 s."
    )
    pl = Plate(f"Planning is {abs(pct(EST)):.0f} % faster", 1010, desc)
    yb = scorecard(pl, morph=False, motion=())
    pl.add(
        text(20, yb + 10, "planning_time · s, median per commit", "mono f-ink2"),
        history_strip(x0=20, x1=780, y0=yb + 26, y1=yb + 170),
    )
    hy = yb + 240
    pl.add(
        text(20, hy, "cycle_time · s, load × speed · m/s", "mono f-ink2"),
        blink_label(pl, 300, hy),
        blink_heat(pl, x0=100, y0=hy + 20, cw=100, ch=40),
    )
    return pl


PLATES = {
    "a_morph_differences.svg": plate_a,
    "b_blink.svg": plate_b,
    "c_metric_source.svg": plate_c,
    "d_trajectory_replay.svg": plate_d,
    "e_change_of_scale.svg": plate_e,
    "f_history.svg": plate_f,
    "g_combo_scorecard_morph.svg": plate_g,
    "h_combo_blink_history.svg": plate_h,
}


def main() -> None:
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
