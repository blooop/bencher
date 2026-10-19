"""Write the statistical-evidence demo plates as standalone animated SVG files.

The data are synthetic and seeded, so every run writes the same files. The script uses
only the standard library:

    python docs/evidence_svg_demo/make_svgs.py

Each SVG carries a light and a dark palette (``prefers-color-scheme``) and uses CSS
``@keyframes`` for its few motions, so ``prefers-reduced-motion`` turns them off. The
resting frame is complete: a reader who sees only the still image gets every number.
"""

# ruff: noqa: PLR2004, RUF001
# PLR2004: a plot is mostly literal coordinates. RUF001: the labels use the real minus
# sign, the approximately-equal sign and arrows on purpose.

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import NamedTuple
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent
W = 920
MASK = 0xFFFFFFFF
HEAD = 66  # height of the plate header (badge, title, use line)

SANS = '-apple-system,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif'
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

# Okabe-Ito marks. The t* tokens are text steps of the same hues, dark enough to read as
# small text on white; on the dark surface the mark colours already pass.
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
    "band": "#E9F0F7",
    "bandEdge": "#B9CCE0",
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
    "band": "#1E2C3A",
    "bandEdge": "#35506B",
    "chip": "#1C2128",
    "white": "#FFFFFF",
}

# verdict kind -> (mark token, text token, glyph, word)
VERDICT = {
    "improved": ("better", "tbetter", "up", "Improved"),
    "regressed": ("worse", "tworse", "down", "Regressed"),
    "equiv": ("ink2", "ink2", "≈", "No change"),
    "small": ("ink2", "ink2", "≈", "Small gain, within ±Δ"),
    "unsure": ("unsure", "tunsure", "?", "Inconclusive"),
}

BASE_CSS = f"""
text{{font-family:{SANS}}}
.mono{{font-family:{MONO}}}
.b{{font-weight:600}}
.bb{{font-weight:700}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes grow{{from{{stroke-dashoffset:1}}to{{stroke-dashoffset:0}}}}
.fade{{animation:fade .45s ease-out both}}
.grow{{stroke-dasharray:1 1;animation:grow 1.1s cubic-bezier(.25,.7,.25,1) .3s both}}
.hop{{opacity:0}}
@media (prefers-reduced-motion:reduce){{.fade,.grow,.hop{{animation:none}}.hopnote{{display:none}}}}
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


class Pair(NamedTuple):
    shard: int
    idx: int
    base: float
    cand: float
    order: str


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
BOOTS: list[float] = []
for _ in range(4000):
    _acc = 0.0
    for _j in range(len(LOG_DIFF)):
        _acc += LOG_DIFF[math.floor(RNG.rnd() * len(LOG_DIFF))]
    BOOTS.append(_acc / len(LOG_DIFF))
EST = sum(LOG_DIFF) / len(LOG_DIFF)
C90 = (quant(BOOTS, 0.05), quant(BOOTS, 0.95))
C95 = (quant(BOOTS, 0.025), quant(BOOTS, 0.975))
MARGIN = math.log(1.05)
N_FASTER = sum(p.cand < p.base for p in PAIRS)


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
    size: float = 12,
    anchor: str | None = None,
    **attrs: object,
) -> str:
    return el("text", escape(s), x=x, y=y, cls=cls, font_size=size, text_anchor=anchor, **attrs)


def line(
    x1: float, y1: float, x2: float, y2: float, cls: str, width: float = 1, **attrs: object
) -> str:
    return el("line", x1=x1, y1=y1, x2=x2, y2=y2, cls=cls, stroke_width=width, **attrs)


def rect(x: float, y: float, w: float, h: float, cls: str, **attrs: object) -> str:
    return el("rect", x=x, y=y, width=w, height=h, cls=cls, **attrs)


def circle(cx: float, cy: float, r: float, cls: str, **attrs: object) -> str:
    return el("circle", cx=cx, cy=cy, r=r, cls=cls, **attrs)


def glyph(shape: str, x: float, y: float, size: float, tok: str) -> tuple[str, float]:
    """Draw a verdict glyph with its left edge at x on baseline y; return it and its advance.

    The triangles are paths, so they do not depend on a font that has U+25B2 and U+25BC.
    """
    if shape in {"up", "down"}:
        w, h = size * 0.72, size * 0.64
        if shape == "up":
            bot = y - size * 0.02
            d = f"M{num(x)} {num(bot)}L{num(x + w / 2)} {num(bot - h)}L{num(x + w)} {num(bot)}Z"
        else:
            top = y - size * 0.68
            d = f"M{num(x)} {num(top)}L{num(x + w)} {num(top)}L{num(x + w / 2)} {num(top + h)}Z"
        return el("path", d=d, cls=f"f-{tok}"), w + size * 0.32
    return text(x, y, shape, f"f-{tok} bb", size), size * 0.62 + size * 0.28


def verdict_text(
    kind: str, x: float, y: float, size: float, words: str | None = None, cls: str = "b"
) -> str:
    _, tok, shape, word = VERDICT[kind]
    g, adv = glyph(shape, x, y, size, tok)
    return g + text(x + adv, y, words if words is not None else word, f"f-{tok} {cls}", size)


def chips(
    x0: float, y0: float, items: list[tuple[str, str]], maxx: float, size: float = 11.5
) -> str:
    """Draw key/value chips in rows, wrapping at maxx."""
    out, cx, cy = [], x0, y0
    for k, v in items:
        w = len(f"{k}  {v}") * size * 0.6 + 16
        if cx + w > maxx:
            cx, cy = x0, cy + 28
        out.append(rect(cx, cy, w, 22, "f-chip", rx=3))
        body = escape(k + "  ") + el("tspan", escape(v), cls="f-ink")
        out.append(el("text", body, x=cx + 8, y=cy + 15, cls="mono f-muted", font_size=size))
        cx += w + 6
    return "".join(out)


def legend_arms(right: float, y: float) -> str:
    out, x = [], right
    for tok, name in (("cand", "candidate (the PR)"), ("base", "base")):
        x -= len(name) * 6.6
        out.append(text(x, y, name, "f-ink2", 12))
        x -= 17
        out.append(rect(x, y - 10, 11, 11, f"f-{tok}", rx=2))
        x -= 14
    return "".join(out)


class Plate:
    def __init__(self, gid: str, title: str, use: str, height: float, desc: str) -> None:
        self.gid, self.title, self.use, self.height, self.desc = gid, title, use, height, desc
        self.parts: list[str] = []
        self.defs: list[str] = []
        self.extra: dict[str, tuple[str, str]] = {}  # class -> (light fill, dark fill)
        self.css = ""
        self.arms = False

    def add(self, *parts: str) -> None:
        self.parts.extend(parts)

    def _palette(self, pal: dict[str, str], col: int) -> str:
        rules = [f".f-{k}{{fill:{v}}}.s-{k}{{stroke:{v}}}" for k, v in pal.items()]
        rules += [f".{k}{{fill:{v[col]}}}" for k, v in self.extra.items()]
        return "".join(rules)

    def render(self) -> str:
        h = HEAD + self.height + 12
        css = (
            BASE_CSS
            + self._palette(LIGHT, 0)
            + "\n@media (prefers-color-scheme:dark){"
            + self._palette(DARK, 1)
            + "}\n"
            + self.css
        )
        bw = len(self.gid) * 7.4 + 14
        head = [
            rect(0.5, 0.5, W - 1, h - 1, "f-plate s-rule", rx=6),
            rect(16, 16, bw, 20, "f-ink", rx=3),
            text(16 + bw / 2, 30.5, self.gid, "mono f-plate", 12, "middle"),
            text(16 + bw + 10, 31, self.title, "f-ink b", 17),
            text(16 + bw + 10, 52, self.use, "mono f-muted", 11.5),
        ]
        if self.arms:
            head.append(legend_arms(W - 16, 31))
        defs = el("defs", "".join(self.defs)) if self.defs else ""
        body = "".join(head) + el("g", "".join(self.parts), transform=f"translate(0,{HEAD})")
        label = f"{self.gid} {self.title}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{num(float(h))}" '
            f'viewBox="0 0 {W} {num(float(h))}" role="img" aria-labelledby="t d">'
            f'<title id="t">{escape(label)}</title><desc id="d">{escape(self.desc)}</desc>'
            f"<style>{css}</style>{defs}{body}</svg>\n"
        )


def eff_axis(x0: float, x1: float, lo: float = math.log(0.68), hi: float = math.log(1.36)):
    return lambda v: x0 + (v - lo) / (hi - lo) * (x1 - x0)


# ---------------------------------------------------------------- plates


def plate_g1() -> Plate:
    tiles = [
        {
            "m": "planning_time",
            "claim": "claim: faster · minimize",
            "big": f"{fmt(pct(EST))} %",
            "ci": f"90 % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}] %",
            "ci_log": C90,
            "pe": EST,
            "v": verdict(-C90[1], -C90[0], MARGIN),
            "foot": ("n=20 pairs · ABBA · 4 shards", "BCa · Holm ×3 primary"),
        },
        {
            "m": "task_success",
            "claim": "claim: more reliable · maximize",
            "big": "+5.6 pp",
            "note": "17/18 → 18/18",
            "ci": "90 % CI [−8.9, +25.8] pp",
            "ci_log": (-0.089, 0.258),
            "pe": 0.056,
            "v": "unsure",
            "bin": True,
            "foot": ("n=18 per arm · Newcombe", "Barnard p=0.50 · MDE 22 pp"),
        },
        {
            "m": "tracking_error_rms",
            "claim": "claim: no regression · minimize",
            "big": "+0.8 %",
            "ci": "90 % CI [−1.9, +3.6] %",
            "ci_log": (math.log(0.981), math.log(1.036)),
            "pe": math.log(1.008),
            "v": "equiv",
            "foot": ("n=20 pairs · TOST 90 %", "margin ±5 % (set before run)"),
        },
    ]
    desc = "; ".join(f"{t['m']} {t['big']}, {t['ci']}, {VERDICT[t['v']][3]}" for t in tiles)
    pl = Plate("G1", "Scorecard", "top of every report · one tile per primary metric", 240, desc)
    for i, t in enumerate(tiles):
        tx, tw = 16 + i * 300, 288
        ix = tx + 14
        mark, _, _, word = VERDICT[t["v"]]
        pl.add(
            rect(tx, 0, tw, 240, "f-plate s-rule", rx=6),
            text(ix, 24, t["m"], "mono f-ink2", 12.5),
            text(ix, 43, t["claim"], "f-muted", 13),
            text(ix, 90, t["big"], "f-ink bb", 40),
            text(ix, 112, t["ci"], "mono f-ink2", 12),
        )
        if "note" in t:
            pl.add(text(tx + tw - 14, 88, t["note"], "mono f-ink2", 12, "end"))
        # mini effect bar, 260 wide, on the shared effect axis with the margin band
        bx, by, bwid = ix, 122, 260
        if t.get("bin"):
            m = 0.05

            def sc(v: float, bx: float = bx, bwid: float = bwid) -> float:
                return bx + bwid / 2 + v / 0.35 * (bwid / 2 - 8)
        else:
            m = MARGIN
            sc = eff_axis(bx + 8, bx + bwid - 8)
        lo, hi = t["ci_log"]
        pe = t["pe"]
        y = by + 15
        pl.add(
            rect(sc(-m), by + 6, sc(m) - sc(-m), 18, "f-band s-bandEdge", stroke_width=1),
            line(sc(0), by + 2, sc(0), by + 28, "s-muted"),
            el(
                "path",
                d=f"M{num(sc(pe))} {y}H{num(sc(lo))}",
                pathLength=1,
                cls=f"s-{mark} grow",
                stroke_width=5,
                stroke_linecap="round",
                fill="none",
            ),
            el(
                "path",
                d=f"M{num(sc(pe))} {y}H{num(sc(hi))}",
                pathLength=1,
                cls=f"s-{mark} grow",
                stroke_width=5,
                stroke_linecap="round",
                fill="none",
            ),
            circle(sc(pe), y, 5.5, f"f-plate s-{mark}", stroke_width=2.5),
            text(sc(-m), by + 34, "−Δ", "mono f-muted", 9.5, "middle"),
            text(sc(m), by + 34, "+Δ", "mono f-muted", 9.5, "middle"),
        )
        # verdict pill: glyph + word, so colour is never alone
        pw = len(word) * 7.7 + 34
        pill = rect(ix, 166, pw, 24, f"s-{mark}", rx=12, fill="none", stroke_width=1.5)
        pl.add(
            el(
                "g",
                pill + verdict_text(t["v"], ix + 10, 183, 14),
                cls="fade",
                style="animation-delay:1.3s",
            ),
            line(ix, 202, tx + tw - 14, 202, "s-rule", stroke_dasharray="3 3"),
            text(ix, 218, t["foot"][0], "mono f-muted", 10.5),
            text(ix, 233, t["foot"][1], "mono f-muted", 10.5),
        )
    return pl


def plate_design() -> Plate:
    desc = (
        "This run is paired ABBA on 4 VMs, 5 pairs each: each pair runs back to back on one VM "
        "and the order alternates. Contrast: a blocked unpaired design runs all base then all "
        "candidate, so drift between blocks lands on the effect."
    )
    pl = Plate(
        "D",
        "Design strip: how the experiment ran",
        "part of every graphic · under G1, G2, G3, G5–G7",
        232,
        desc,
    )
    pl.arms = True
    cell, gap, x0, y0 = 16, 4, 16, 22
    pl.add(text(x0, y0, "This run: paired, ABBA, 4 VMs", "f-ink b", 13))
    for r in range(4):
        pl.add(text(x0, y0 + 24 + r * (cell + gap) + 12, f"VM {r + 1}", "mono f-muted", 11))
        seq: list[str] = []
        for p in range(5):
            seq += ["B", "A"] if p % 2 else ["A", "B"]
        for i, a in enumerate(seq):
            x = x0 + 44 + i * (cell + gap) + (i // 2) * 6
            delay = 0.2 + i * 0.13 + r * 0.03
            pl.add(
                rect(
                    x,
                    y0 + 24 + r * (cell + gap),
                    cell,
                    cell,
                    f"f-{'base' if a == 'A' else 'cand'} fade",
                    rx=3,
                    style=f"animation-delay:{delay:.2f}s",
                )
            )
    pl.add(
        text(
            x0,
            y0 + 24 + 4 * (cell + gap) + 16,
            "each pair runs back to back on one VM; the order alternates",
            "f-ink2",
            11.5,
        )
    )
    bx = 526
    pl.add(text(bx, 22, "For contrast: blocked, unpaired", "f-ink b", 13))
    for k, a in enumerate("AB"):
        for i in range(10):
            x = bx + 44 + i * (cell + gap) / 2 + k * (10 * (cell + gap) / 2 + 14)
            pl.add(
                rect(
                    x,
                    46,
                    cell / 2 + 2,
                    cell * 2 + gap,
                    f"f-{'base' if a == 'A' else 'cand'} fade",
                    rx=2,
                    style=f"animation-delay:{1.9 + k * 0.6:.1f}s",
                )
            )
    pl.add(
        text(bx, 58, "VM 1", "mono f-muted", 11),
        text(bx + 44, 100, "all base, then all candidate:", "f-ink2", 11.5),
        text(bx + 44, 116, "drift between blocks lands on the effect", "f-tworse", 11.5),
        line(60, 154, 470, 154, "s-muted"),
        el("path", d="M470 150L478 154L470 158Z", cls="f-muted"),
        text(486, 158, "run order", "mono f-muted", 10.5),
        chips(
            16,
            176,
            [
                ("design", "paired · ABBA"),
                ("unit", "pair, clustered by VM"),
                ("n", "20 pairs = 4 VMs × 5"),
                ("seed", "same seed per pair"),
                ("margin", "±5 % (set before run)"),
                ("test", "BCa, paired log diff, 90 % CI"),
                ("family", "Holm × 3 primary"),
            ],
            W - 16,
        ),
    )
    return pl


def plate_g2() -> Plate:
    lg = math.log
    rows = [
        ("planning_time", "min", EST, C90, C95, True),
        (
            "time_to_simulating",
            "min",
            lg(0.93),
            (lg(0.905), lg(0.957)),
            (lg(0.90), lg(0.962)),
            True,
        ),
        ("trajectory_time", "min", lg(0.975), (lg(0.93), lg(1.02)), (lg(0.92), lg(1.03)), True),
        ("path_length", "min", lg(0.995), (lg(0.98), lg(1.01)), (lg(0.977), lg(1.013)), True),
        (
            "tracking_error_rms",
            "min",
            lg(1.008),
            (lg(0.981), lg(1.036)),
            (lg(0.976), lg(1.041)),
            True,
        ),
        ("smoothness", "max", lg(1.003), (lg(0.988), lg(1.019)), (lg(0.985), lg(1.022)), True),
        ("startup_time", "min", lg(1.01), (lg(0.97), lg(1.045)), (lg(0.962), lg(1.052)), True),
        ("shutdown_time", "min", lg(1.0), (lg(0.965), lg(1.04)), (lg(0.957), lg(1.049)), True),
        ("pos_error", "min", lg(1.02), (lg(0.99), lg(1.048)), (lg(0.985), lg(1.055)), True),
        ("yaw_error", "min", lg(0.99), (lg(0.968), lg(1.012)), (lg(0.962), lg(1.018)), True),
        ("plan_path_stretch", "min", lg(1.0), (lg(0.982), lg(1.018)), (lg(0.978), lg(1.022)), True),
        (
            "tracking_error_max",
            "min",
            lg(1.06),
            (lg(0.99), lg(1.135)),
            (lg(0.975), lg(1.15)),
            False,
        ),
    ]
    rows.sort(key=lambda r: r[2])
    top, rh = 40, 26
    height = top + len(rows) * rh + 80
    kinds = []
    for _name, d, _, a, _, _ in rows:
        k = verdict(a[0], a[1], MARGIN) if d == "max" else verdict(-a[1], -a[0], MARGIN)
        kinds.append(k)
    counts = {k: kinds.count(k) for k in VERDICT}
    desc = (
        f"Forest plot of 12 metrics on one log-ratio axis with a ±5 % margin: "
        f"{counts['improved']} improved, {counts['regressed']} regressed, "
        f"{counts['equiv'] + counts['small']} within the margin, {counts['unsure']} inconclusive."
    )
    pl = Plate(
        "G2", "Forest plot: 12 metrics on one axis", "many metrics or sweep points", height, desc
    )
    x0, x1 = 200, 720
    sc = eff_axis(x0, x1, math.log(0.74), math.log(1.22))
    bot = top + len(rows) * rh
    pl.add(rect(sc(-MARGIN), top - 8, sc(MARGIN) - sc(-MARGIN), len(rows) * rh + 8, "f-band"))
    for p in (-20, -10, 0, 10, 20):
        x = sc(math.log(1 + p / 100))
        pl.add(
            line(x, top - 8, x, bot, "s-muted" if p == 0 else "s-grid"),
            text(
                x,
                bot + 18,
                f"{'+' if p > 0 else ''}{p} %".replace("-", "−"),
                "mono f-muted",
                11,
                "middle",
            ),
        )
    pl.add(
        text(sc(-MARGIN), top - 14, "−5 %", "mono f-muted", 10.5, "middle"),
        text(sc(MARGIN), top - 14, "+5 %", "mono f-muted", 10.5, "middle"),
        text(sc(0), top - 26, "±Δ margin", "f-muted", 10.5, "middle"),
        text(x0, height - 10, "← candidate lower", "f-muted", 11),
        text(x1, height - 10, "candidate higher →", "f-muted", 11, "end"),
        text(
            (x0 + x1) / 2,
            height - 10,
            "design: paired ABBA · 20 pairs · 4 VMs",
            "mono f-muted",
            11,
            "middle",
        ),
        text(740, top - 14, "verdict", "mono f-muted", 11),
        text(905, top - 14, "change", "mono f-muted", 11, "end"),
    )
    for i, ((name, d, e, a, b, fdr), k) in enumerate(zip(rows, kinds, strict=True)):
        y = top + i * rh + 8
        mark = VERDICT[k][0]
        words = {"small": "small gain"}.get(k)
        pl.add(
            text(x0 - 12, y + 4, name, "mono f-ink", 12.5, "end"),
            text(
                x0 - 12 - len(name) * 7.6 - 8,
                y + 4,
                "↓" if d == "min" else "↑",
                "f-muted",
                11,
                "end",
            ),
            line(sc(b[0]), y, sc(b[1]), y, f"s-{mark}", 1.5, stroke_linecap="round"),
            line(sc(a[0]), y, sc(a[1]), y, f"s-{mark}", 5, stroke_linecap="round"),
            circle(
                sc(e), y, 5, f"f-{mark} s-plate" if fdr else f"f-plate s-{mark}", stroke_width=2
            ),
            verdict_text(k, 740, y + 4, 12, words),
            text(905, y + 4, f"{fmt(pct(e))} %", "mono f-ink2", 12, "end"),
        )
    ky = height - 36
    pl.add(
        line(x0, ky, x0 + 28, ky, "s-ink2", 5, stroke_linecap="round"),
        text(x0 + 36, ky + 4, "90 % CI", "f-muted", 11),
        line(x0 + 96, ky, x0 + 124, ky, "s-ink2", 1.5),
        text(x0 + 132, ky + 4, "95 % CI", "f-muted", 11),
        circle(x0 + 196, ky, 5, "f-plate s-ink2", stroke_width=2),
        text(x0 + 206, ky + 4, "hollow: failed BH-FDR", "f-muted", 11),
    )
    return pl


def plate_g3() -> Plate:
    desc = (
        f"planning_time, paired: {N_FASTER} of 20 pairs faster. Effect {fmt(pct(EST))} %, "
        f"90 % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}] %, beyond the ±5 % margin: improved."
    )
    pl = Plate(
        "G3",
        f"Estimation plot: planning is {abs(pct(EST)):.0f} % faster",
        "each primary continuous metric",
        418,
        desc,
    )
    pl.arms = True
    y_t, y_b, lo, hi = 40, 320, 0.2, 0.72

    def ys(v: float) -> float:
        return y_b - (v - lo) / (hi - lo) * (y_b - y_t)

    for v in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
        pl.add(
            line(70, ys(v), 520, ys(v), "s-grid"),
            text(62, ys(v) + 4, f"{v:.1f}", "mono f-muted", 11, "end"),
        )
    pl.add(text(20, y_t - 18, "planning_time (s) · every sample", "f-ink2", 12))
    xa, xb = 180, 410
    for i, p in enumerate(PAIRS):
        j = (i % 10 - 4.5) * 3
        faster = p.cand < p.base
        pl.add(
            line(
                xa + j,
                ys(p.base),
                xb + j,
                ys(p.cand),
                "s-cand" if faster else "s-worse",
                1.5,
                stroke_opacity=0.35 if faster else 0.8,
            )
        )
    for i, p in enumerate(PAIRS):
        j = (i % 10 - 4.5) * 3
        pl.add(
            circle(xa + j, ys(p.base), 4, "f-base s-plate", stroke_width=1.5),
            circle(xb + j, ys(p.cand), 4, "f-cand s-plate", stroke_width=1.5),
        )
    mb, mc = quant([p.base for p in PAIRS], 0.5), quant([p.cand for p in PAIRS], 0.5)
    pl.add(
        line(xa - 36, ys(mb), xa + 36, ys(mb), "s-base", 3),
        line(xb - 36, ys(mc), xb + 36, ys(mc), "s-cand", 3),
        text(xa - 40, ys(mb) + 4, f"median {mb:.2f}", "mono f-ink2", 11, "end"),
        text(xb + 40, ys(mc) + 4, f"median {mc:.2f}", "mono f-ink2", 11),
        text(xa, y_b + 24, "base", "f-ink b", 13, "middle"),
        text(xb, y_b + 24, "candidate", "f-ink b", 13, "middle"),
        text(
            295,
            y_b + 46,
            f"one line per pair · {N_FASTER} of 20 pairs faster",
            "f-muted",
            11.5,
            "middle",
        ),
    )
    ex, ex1, e_t, e_b = 560, 900, 40, 320
    elo, ehi = math.log(0.72), math.log(1.12)

    def es(v: float) -> float:
        return e_b - (v - elo) / (ehi - elo) * (e_b - e_t)

    pl.add(
        text(ex, y_t - 18, "paired effect · bootstrap distribution", "f-ink2", 12),
        rect(ex + 40, es(MARGIN), ex1 - ex - 40, es(-MARGIN) - es(MARGIN), "f-band"),
        text(ex1 - 4, es(MARGIN) - 4, "±Δ 5 %", "mono f-muted", 10.5, "end"),
    )
    for p in (-25, -20, -15, -10, -5, 0, 5, 10):
        y = es(math.log(1 + p / 100))
        pl.add(
            line(ex + 40, y, ex1, y, "s-muted" if p == 0 else "s-grid"),
            text(
                ex + 32,
                y + 4,
                f"{'+' if p > 0 else ''}{p} %".replace("-", "−"),
                "mono f-muted",
                11,
                "end",
            ),
        )
    bins = 60
    hist = [0] * bins
    for b in BOOTS:
        k = math.floor((b - elo) / (ehi - elo) * bins)
        if 0 <= k < bins:
            hist[k] += 1
    hm, vx = max(hist), ex + 110
    d = f"M{vx} {num(es(elo))}"
    for k, hv in enumerate(hist):
        d += f"L{num(vx + hv / hm * 150)} {num(es(elo + (k + 0.5) / bins * (ehi - elo)))}"
    d += f"L{vx} {num(es(ehi))}Z"
    nz = [k for k, hv in enumerate(hist) if hv]
    k0, k1 = max(nz[0] - 1, 0), min(nz[-1] + 1, bins - 1)
    edge = "".join(
        f"{'L' if k > k0 else 'M'}{num(vx + hist[k] / hm * 150)} {num(es(elo + (k + 0.5) / bins * (ehi - elo)))}"
        for k in range(k0, k1 + 1)
    )
    pl.add(
        el("path", d=d, cls="f-better", fill_opacity=0.22),
        el("path", d=edge, cls="s-better", fill="none", stroke_width=1.2),
        line(vx - 14, es(C95[0]), vx - 14, es(C95[1]), "s-better", 1.5),
        line(vx - 14, es(C90[0]), vx - 14, es(C90[1]), "s-better", 6, stroke_linecap="round"),
        circle(vx - 14, es(EST), 6, "f-better s-plate", stroke_width=2),
    )
    # Hypothetical outcome plot: a faint marker and tick visit a few bootstrap draws, one
    # per 1.2 s with a soft fade. It sits on top of the static estimate, CI and density.
    draws = BOOTS[:6]
    seg = 100 / len(draws)
    frames = []
    for k, dv in enumerate(draws):
        dy = num(es(dv) - es(EST))
        a = k * seg
        for f, op in ((0, 0), (0.3, 0.7), (0.7, 0.7), (0.995, 0)):
            frames.append(f"{a + f * seg:.2f}%{{transform:translateY({dy}px);opacity:{op}}}")
    pl.css = (
        "@keyframes hop{" + "".join(frames) + "}"
        f".hop{{animation:hop {1.2 * len(draws):.1f}s linear 1.5s infinite}}"
    )
    y0 = es(EST)
    pl.add(
        el(
            "g",
            line(vx - 26, y0, vx + 120, y0, "s-ink2", 1.2)
            + circle(vx - 14, y0, 4.5, "f-plate s-ink2", stroke_width=1.5),
            cls="hop",
        ),
        text(vx + 40, e_b - 28, f"{fmt(pct(EST))} %", "f-ink bb", 30),
        text(
            vx + 40,
            e_b - 10,
            f"90 % CI [{fmt(pct(C90[0]))}, {fmt(pct(C90[1]))}]",
            "mono f-ink2",
            12,
        ),
        verdict_text("improved", vx + 40, e_b + 8, 13, "Improved, beyond ±Δ"),
        text(ex, y_b + 30, "BCa bootstrap of paired log diffs · 4000 draws", "mono f-muted", 11),
        text(ex, y_b + 46, "Wilcoxon signed-rank p < 0.001 · agrees", "mono f-muted", 11),
        text(ex, y_b + 62, "faint tick: one bootstrap draw at a time", "f-muted hopnote", 10.5),
        chips(
            20,
            394,
            [
                ("design", "paired · ABBA"),
                ("n", "20 pairs = 4 VMs × 5"),
                ("margin", "±5 %"),
                ("test", "BCa, 90 % CI"),
            ],
            W - 16,
            11,
        ),
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
    x0, x1, lo, hi = 110, 880, 0.1, 1.0

    def xs(v: float) -> float:
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    dec = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    shifts = []
    for p in dec:
        diffs = []
        for _ in range(600):
            ra = [arm_a[math.floor(RNG.rnd() * n)] for _ in arm_a]
            rb = [arm_b[math.floor(RNG.rnd() * n)] for _ in arm_b]
            diffs.append(quant(rb, p) - quant(ra, p))
        shifts.append(
            (p, quant(arm_b, p) - quant(arm_a, p), quant(diffs, 0.025), quant(diffs, 0.975))
        )
    p90 = shifts[-1]
    desc = (
        f"Latency raincloud, 60 runs per arm. Median shift (CI holds 0) {fmt(shifts[4][1] * 1000, 0)} ms; "
        f"p90 shift {fmt(p90[1] * 1000, 0)} ms, 95 % CI [{fmt(p90[2] * 1000, 0)}, {fmt(p90[3] * 1000, 0)}] ms."
    )
    pl = Plate(
        "G4",
        "Raincloud and shift function: the tail moved, the median did not",
        "heavy tails, p95 / p99 claims, bimodal data",
        450,
        desc,
    )
    pl.arms = True
    for v in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        pl.add(
            line(xs(v), 20, xs(v), 230, "s-grid"),
            text(xs(v), 246, f"{v:.1f} s", "mono f-muted", 11, "middle"),
        )

    def cloud(arr: list[float], yc: float, tok: str, name: str) -> None:
        bw, pts = 0.03, []
        for k in range(121):
            x = lo + k / 120 * (hi - lo)
            pts.append((x, sum(math.exp(-(((x - a) / bw) ** 2) / 2) for a in arr)))
        m = max(p[1] for p in pts)
        d = f"M{num(xs(lo))} {yc}" + "".join(
            f"L{num(xs(x))} {num(yc - v / m * 58)}" for x, v in pts
        )
        d += f"L{num(xs(hi))} {yc}Z"
        q1, q3, md, q9 = quant(arr, 0.25), quant(arr, 0.75), quant(arr, 0.5), quant(arr, 0.9)
        pl.add(
            el("path", d=d, cls=f"f-{tok} s-{tok}", fill_opacity=0.25, stroke_width=1.5),
            rect(xs(q1), yc + 6, xs(q3) - xs(q1), 10, f"f-{tok}", rx=2, fill_opacity=0.9),
            line(xs(md), yc + 3, xs(md), yc + 19, "s-plate", 2.5),
            line(xs(q9), yc + 3, xs(q9), yc + 19, f"s-{tok}", 2),
            text(xs(q9) + 4, yc + 16, "p90", "mono f-muted", 10),
            *(
                circle(xs(a), yc + 26 + (i % 5) * 4, 2.4, f"f-{tok}", fill_opacity=0.75)
                for i, a in enumerate(arr)
            ),
            text(x0 - 12, yc + 4, name, "f-ink b", 13, "end"),
        )

    cloud(arm_a, 82, "base", "base")
    cloud(arm_b, 184, "cand", "candidate")
    sy0, sy1, dlo, dhi = 290, 390, -0.38, 0.08

    def ys(v: float) -> float:
        return sy1 - (v - dlo) / (dhi - dlo) * (sy1 - sy0)

    pl.add(
        text(
            20, sy0 - 14, "shift function · candidate − base at each decile, 95 % CI", "f-ink2", 12
        ),
        text(x1, sy0 - 14, "filled: CI excludes 0", "f-muted", 11, "end"),
    )
    for v in (-0.3, -0.2, -0.1, 0):
        lab = f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v * 1000):.0f} ms"
        pl.add(
            line(x0, ys(v), x1, ys(v), "s-muted" if v == 0 else "s-grid"),
            text(x0 - 8, ys(v) + 4, lab, "mono f-muted", 10.5, "end"),
        )
    step = (x1 - x0) / (len(dec) + 1)
    for k, (p, dv, lo_ci, hi_ci) in enumerate(shifts):
        x = x0 + (k + 1) * step
        sig = hi_ci < 0 or lo_ci > 0
        tok = ("better" if hi_ci < 0 else "worse") if sig else "muted"
        pl.add(
            line(
                x,
                ys(max(lo_ci, dlo)),
                x,
                ys(min(hi_ci, dhi)),
                f"s-{tok}",
                2.5,
                stroke_linecap="round",
            ),
            circle(x, ys(dv), 5, f"f-{tok} s-{tok}" if sig else f"f-plate s-{tok}", stroke_width=2),
            text(x, sy1 + 18, f"q{round(p * 10)}", "mono f-muted", 10.5, "middle"),
        )
    pl.add(
        chips(
            20,
            420,
            [
                ("design", "unpaired · interleaved"),
                ("n", "60 runs per arm"),
                ("CI", "bootstrap of deciles, 600 resamples"),
            ],
            W - 16,
            11,
        )
    )
    return pl


def plate_g5() -> Plate:
    desc = (
        "task_success 17/18 to 18/18: +5.6 pp, 90 % CI [−8.9, +25.8], inconclusive. "
        "required_sigkill flake: base 4/30, candidate 0/30, true rate at most 10 % (rule of three): improved."
    )
    pl = Plate(
        "G5",
        "Waffle: success rates and flakes",
        "binary metrics: task_success, clean_exit",
        300,
        desc,
    )
    pl.arms = True

    def waffle(x0: float, y0: float, n: int, fails: int, tok: str, cols: int) -> None:
        c, g = 14, 3
        for i in range(n):
            r, k = divmod(i, cols)
            x, y = x0 + k * (c + g), y0 + r * (c + g)
            fail = i >= n - fails
            delay = 0.25 + i * 0.05 + (0.4 if fail else 0)
            style = f"animation-delay:{delay:.2f}s"
            if fail:
                body = rect(x, y, c, c, "f-plate s-worse", rx=2.5, stroke_width=2) + el(
                    "path", d=f"M{x + 3.5} {y + 3.5}l7 7m0 -7l-7 7", cls="s-worse", stroke_width=1.8
                )
                pl.add(el("g", body, cls="fade", style=style))
            else:
                pl.add(rect(x, y, c, c, f"f-{tok} fade", rx=2.5, style=style))

    pl.add(
        text(16, 22, "task_success · 18 runs per arm", "f-ink b", 13),
        text(16, 58, "base", "f-ink2", 12),
        text(16, 108, "candidate", "f-ink2", 12),
    )
    waffle(90, 46, 18, 1, "base", 9)
    waffle(90, 96, 18, 0, "cand", 9)
    pl.add(
        text(260, 58, "17/18 · 94 % [74, 99]", "mono f-ink2", 12),
        text(260, 108, "18/18 · 100 % [82, 100]", "mono f-ink2", 12),
    )
    x0, x1 = 90, 430

    def sc(v: float) -> float:
        return x0 + (v + 0.3) / 0.6 * (x1 - x0)

    pl.add(rect(sc(-0.05), 150, sc(0.05) - sc(-0.05), 26, "f-band"))
    for v in (-0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3):
        lab = f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v * 100):.0f} pp"
        pl.add(
            line(sc(v), 146, sc(v), 180, "s-muted" if v == 0 else "s-grid"),
            text(sc(v), 196, lab, "mono f-muted", 10.5, "middle"),
        )
    pl.add(
        line(sc(-0.089), 163, sc(0.258), 163, "s-unsure", 5, stroke_linecap="round"),
        circle(sc(0.056), 163, 5.5, "f-plate s-unsure", stroke_width=2.5),
        text(16, 167, "difference", "f-ink2", 12),
        verdict_text("unsure", 90, 226, 13, "Inconclusive: +5.6 pp, 90 % CI [−8.9, +25.8]"),
        text(
            90,
            246,
            "Newcombe CI · Barnard p = 0.50 · this n sees only ≥ 22 pp",
            "mono f-muted",
            11.5,
        ),
    )
    fx = 500
    pl.add(
        text(fx, 22, "required_sigkill · flake fixed?", "f-ink b", 13),
        text(fx, 58, "base", "f-ink2", 12),
        text(fx, 108, "candidate", "f-ink2", 12),
    )
    waffle(fx + 80, 46, 30, 4, "base", 15)
    waffle(fx + 80, 96, 30, 0, "cand", 15)
    rx0, rx1 = fx, 900

    def rs(n: float) -> float:
        return rx0 + n / 300 * (rx1 - rx0)

    pl.add(
        text(fx, 152, "base: 4 / 30 runs killed (13 %)", "mono f-ink2", 12),
        text(
            fx, 172, "candidate: 0 / 30 → true rate ≤ 10 % (95 %, rule of three)", "mono f-ink2", 11
        ),
        rect(rx0, 196, rx1 - rx0, 10, "f-chip", rx=5),
        rect(rx0, 196, rs(30) - rx0, 10, "f-cand", rx=5),
    )
    for n, lab in ((29, "10 %"), (59, "5 %"), (299, "1 %")):
        pl.add(
            line(rs(n), 190, rs(n), 212, "s-ink2", 1.5),
            text(
                rs(n),
                226,
                f"{n} runs → ≤{lab}",
                "mono f-muted",
                10.5,
                {29: "end", 59: "start"}.get(n, "end"),
            ),
        )
    pl.add(
        text(fx, 250, "clean runs needed to bound the flake rate at 95 %", "f-muted", 11.5),
        verdict_text(
            "improved", fx, 268, 13, "Improved: 13 % → ≤ 10 %; run 29 more to claim ≤ 5 %"
        ),
    )
    return pl


def plate_g6() -> Plate:
    sp = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6]
    base = [0.9 + 1.1 * v for v in sp]
    eff = [0.0 if v < 0.6 else -0.06 - 0.08 * (v - 0.6) for v in sp]
    se = 0.025
    cand = [b * math.exp(e) for b, e in zip(base, eff, strict=True)]
    desc = "task_duration over 8 speeds: " + "; ".join(
        f"{v} m/s {fmt(pct(e))} %" for v, e in zip(sp, eff, strict=True)
    )
    pl = Plate(
        "G6", "Sweep panel: faster at every speed above 0.6 m/s", "one swept input", 420, desc
    )
    x0, x1 = 90, 820

    def xs(i: int) -> float:
        return x0 + i / (len(sp) - 1) * (x1 - x0)

    t0, t1, lo, hi = 30, 190, 1.0, 2.9

    def ys(v: float) -> float:
        return t1 - (v - lo) / (hi - lo) * (t1 - t0)

    for v in (1.0, 1.5, 2.0, 2.5):
        pl.add(
            line(x0, ys(v), x1, ys(v), "s-grid"),
            text(x0 - 8, ys(v) + 4, f"{v:.1f} s", "mono f-muted", 10.5, "end"),
        )
    pl.add(text(16, 18, "task_duration · median and 90 % CI per point", "f-ink2", 12))
    for arr, tok, name in ((base, "base", "base"), (cand, "cand", "candidate")):
        up = "".join(
            f"{'L' if i else 'M'}{num(xs(i))} {num(ys(v * 1.03))}" for i, v in enumerate(arr)
        )
        dn = "".join(f"L{num(xs(i))} {num(ys(arr[i] * 0.97))}" for i in reversed(range(len(arr))))
        ln = "".join(f"{'L' if i else 'M'}{num(xs(i))} {num(ys(v))}" for i, v in enumerate(arr))
        pl.add(
            el("path", d=up + dn + "Z", cls=f"f-{tok}", fill_opacity=0.15),
            el("path", d=ln, cls=f"s-{tok}", fill="none", stroke_width=2.5),
        )
        pl.add(
            *(
                circle(xs(i), ys(v), 3.5, f"f-{tok} s-plate", stroke_width=1.5)
                for i, v in enumerate(arr)
            )
        )
        pl.add(text(xs(len(arr) - 1) + 8, ys(arr[-1]) + 4, name, "f-ink b", 12))
    b0, b1, elo, ehi = 230, 370, math.log(0.8), math.log(1.08)

    def es(v: float) -> float:
        return b1 - (v - elo) / (ehi - elo) * (b1 - b0)

    pl.add(
        text(16, b0 - 12, "effect per point · % change, 90 % CI", "f-ink2", 12),
        rect(x0, es(MARGIN), x1 - x0, es(-MARGIN) - es(MARGIN), "f-band"),
    )
    for p in (-15, -10, -5, 0, 5):
        y = es(math.log(1 + p / 100))
        pl.add(
            line(x0, y, x1, y, "s-muted" if p == 0 else "s-grid"),
            text(
                x0 - 8,
                y + 4,
                f"{'+' if p > 0 else ''}{p} %".replace("-", "−"),
                "mono f-muted",
                10.5,
                "end",
            ),
        )
    for i, v in enumerate(sp):
        lo_ci, hi_ci = eff[i] - 1.645 * se, eff[i] + 1.645 * se
        k = verdict(-hi_ci, -lo_ci, MARGIN)
        mark, _, shape, _ = VERDICT[k]
        fdr = i != 2
        g, adv = glyph(shape, 0, es(hi_ci) - 8, 12, VERDICT[k][1])
        pl.add(
            line(xs(i), es(lo_ci), xs(i), es(hi_ci), f"s-{mark}", 5, stroke_linecap="round"),
            circle(
                xs(i),
                es(eff[i]),
                5,
                f"f-{mark} s-plate" if fdr else f"f-plate s-{mark}",
                stroke_width=2,
            ),
            text(xs(i), b1 + 18, f"{v:.1f}", "mono f-muted", 11, "middle"),
            el("g", g, transform=f"translate({num(xs(i) - (adv - 3.8) / 2)},0)"),
        )
    pl.add(
        text(
            (x0 + x1) / 2,
            b1 + 38,
            "speed (m/s) · 8 points × 6 paired repeats · BH-FDR over 8 points · hollow: failed FDR",
            "f-muted",
            11.5,
            "middle",
        )
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
        f"cycle_time % change over speed and payload, 20 cells: best {fmt(best[2], 0)} % at "
        f"{sp[best[1]]} m/s and {mass[best[0]]} kg; {n_un} cells inconclusive (hatched)."
    )
    pl = Plate(
        "G7", "Effect heatmap: the gain is in heavy, fast picks", "two swept inputs", 330, desc
    )
    pl.defs.append(
        el(
            "pattern",
            rect(0, 0, 7, 7, "f-plate") + line(0, 0, 0, 7, "s-muted", 1.4, stroke_opacity=0.55),
            id="hatch",
            width=7,
            height=7,
            patternUnits="userSpaceOnUse",
            patternTransform="rotate(45)",
        )
    )

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

    x0, y0, cw, ch = 120, 30, 110, 50
    for r, m in enumerate(mass):
        pl.add(text(x0 - 12, y0 + r * ch + ch / 2 + 4, f"{m} kg", "mono f-muted", 11.5, "end"))
    for r, k, p, kind in cells:
        x, y = x0 + k * cw, y0 + r * ch
        unsure = kind == "unsure"
        fill = "url(#hatch)" if unsure else None
        cls = "s-rule" if unsure else colour_class(p)
        dark = abs(p) > 9 and not unsure
        label = f"{fmt(p, 0)} %"
        tw = len(label) * 7.8
        tok = "f-white" if dark else "f-ink"
        _, _, shape, _ = VERDICT[kind]
        g, adv = glyph(shape, 0, 0, 13, "white" if dark else "ink")
        sx = x + cw / 2 - (adv + tw) / 2
        pl.add(
            rect(x + 1, y + 1, cw - 2, ch - 2, cls, rx=3, fill=fill),
            el("g", g, transform=f"translate({num(sx)},{num(y + ch / 2 + 5)})"),
            text(sx + adv, y + ch / 2 + 5, label, f"mono {tok}", 13, font_weight=500),
        )
    for k, v in enumerate(sp):
        pl.add(
            text(
                x0 + k * cw + cw / 2,
                y0 + len(mass) * ch + 18,
                f"{v} m/s",
                "mono f-muted",
                11.5,
                "middle",
            )
        )
    pl.add(
        text(x0 + 2 * cw, y0 + len(mass) * ch + 38, "speed", "f-ink2", 12, "middle"),
        text(20, y0 - 12, "payload ↓ · cycle_time % change", "f-ink2", 12),
    )
    lx, ly = 620, 60
    pl.add(text(lx, ly - 14, "% change (lower is better)", "f-ink2", 11.5))
    for i in range(31):
        p = -15 + i
        pl.add(rect(lx + i * 8, ly, 8.5, 14, colour_class(p)))
    for p in (-15, -5, 0, 5, 15):
        pl.add(
            text(
                lx + (p + 15) * 8 + 4,
                ly + 30,
                f"{'+' if p > 0 else ''}{p}".replace("-", "−"),
                "mono f-muted",
                10.5,
                "middle",
            )
        )
    pl.add(
        rect(lx, ly + 48, 28, 18, "s-rule", rx=2, fill="url(#hatch)"),
        text(lx + 36, ly + 61, "? CI crosses the ±5 % margin", "f-ink2", 11.5),
        text(lx, ly + 96, "20 cells · 6 paired repeats each", "mono f-muted", 11),
        text(lx, ly + 114, "BH-FDR q = 0.05 over 20 cells", "mono f-muted", 11),
        text(lx, ly + 148, "grid that ran (5 payloads × 4 speeds)", "f-ink2", 11.5),
    )
    for r in range(len(mass)):
        for k in range(len(sp)):
            pl.add(circle(lx + 6 + k * 12, ly + 162 + r * 10, 3, "f-ink2"))
    return pl


def plate_g8() -> Plate:
    desc = "Underpowered: n = 8 per arm can see 9.2 % or more; the claim needs 5 %. About 28 runs per arm reach the margin."
    pl = Plate(
        "G8",
        "Power bar: this run can see 9 %, the claim needs 5 %",
        "under any underpowered verdict",
        150,
        desc,
    )
    x0, x1 = 40, 880

    def sc(p: float) -> float:
        return x0 + p / 14 * (x1 - x0)

    pl.add(
        rect(x0, 40, x1 - x0, 22, "f-chip", rx=4),
        rect(x0, 40, sc(5) - x0, 22, "f-band s-bandEdge", rx=4),
        rect(x0, 46, sc(9.2) - x0, 10, "f-unsure", rx=5),
        line(sc(5), 32, sc(5), 70, "s-ink", 2),
        text(sc(5), 26, "margin Δ = 5 %", "f-ink b", 12, "middle"),
        text(sc(9.2) + 8, 56, "MDE 9.2 % (80 % power)", "mono f-ink2", 12),
        *(text(sc(p), 82, f"{p} %", "mono f-muted", 10.5, "middle") for p in range(0, 15, 2)),
        verdict_text(
            "unsure",
            x0,
            112,
            13,
            "Underpowered: n = 8 per arm can see a change of 9.2 % or more, the claim needs 5 %.",
        ),
        text(
            x0,
            132,
            "Add about 20 runs per arm (n ≈ 8 × (9.2 / 5)² ≈ 28), or pair the runs on one VM.",
            "f-ink2",
            12,
        ),
    )
    return pl


def plate_g9() -> Plate:
    desc = "planning_time against run order, 40 runs on 4 VMs. No slope inside an arm, so no drift. VM 2 runs 12 % slow on both arms; pairing removes it."
    pl = Plate(
        "G9", "Diagnostics: run order and the A/A noise floor", "inside <details>", 260, desc
    )
    pl.arms = True
    x0, x1, y0, y1, n, lo, hi = 70, 880, 30, 200, 40, 0.17, 0.64

    def xs(i: float) -> float:
        return x0 + i / (n - 1) * (x1 - x0)

    def ys(v: float) -> float:
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    med = quant([p.base for p in PAIRS], 0.5)
    pl.add(
        rect(x0, ys(med * 1.03), x1 - x0, ys(med * 0.97) - ys(med * 1.03), "f-band"),
        text(x1, 18, "band: A/A noise floor of base, ±3 %", "mono f-muted", 11, "end"),
    )
    for v in (0.2, 0.3, 0.4, 0.5, 0.6):
        pl.add(
            line(x0, ys(v), x1, ys(v), "s-grid"),
            text(x0 - 8, ys(v) + 4, f"{v:.1f} s", "mono f-muted", 10.5, "end"),
        )
    i = 0
    for p in PAIRS:
        seq = [("A", p.base), ("B", p.cand)] if p.order == "AB" else [("B", p.cand), ("A", p.base)]
        for a, v in seq:
            pl.add(
                circle(
                    xs(i),
                    ys(v),
                    4.5,
                    f"f-{'base' if a == 'A' else 'cand'} s-plate",
                    stroke_width=1.5,
                )
            )
            i += 1
    for k in range(1, 4):
        x = (xs(k * 10 - 1) + xs(k * 10)) / 2
        pl.add(line(x, y0, x, y1, "s-rule", stroke_dasharray="3 3"))
    for k in range(4):
        pl.add(
            text(
                (xs(k * 10) + xs(k * 10 + 9)) / 2,
                y1 + 18,
                f"VM {k + 1}",
                "mono f-muted",
                11,
                "middle",
            )
        )
    pl.add(
        text(
            x0,
            y1 + 42,
            "run order → · no slope inside an arm, so no drift · VM 2 runs 12 % slow on both arms; pairing removes it",
            "f-ink2",
            11.5,
        ),
        text(x0, 18, "planning_time by run order", "f-ink2", 12),
    )
    return pl


def _wrap(s: str, width: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return [*lines, cur]


def plate_dont() -> Plate:
    desc = "Charts the report does not draw: radar charts, bars of means with error bars, and 'p > 0.05, unchanged'."
    pl = Plate("×", "What the report does not draw", "and why", 268, desc)

    def radar(ox: float) -> str:
        cx, cy, r, k = ox + 150, 80, 62, 6

        def poly(vals: list[float]) -> str:
            pts = []
            for i in range(k):
                a = i / k * 2 * math.pi - math.pi / 2
                pts.append(
                    f"{'L' if i else 'M'}{num(cx + math.cos(a) * r * vals[i])} {num(cy + math.sin(a) * r * vals[i])}"
                )
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

    def bars(ox: float) -> str:
        out = [line(ox + 40, 140, ox + 280, 140, "s-muted")]
        for x, tok, h in ((ox + 90, "base", 95), (ox + 190, "cand", 80)):
            out += [
                rect(x - 30, 140 - h, 60, h, f"f-{tok}", rx=2),
                line(x, 140 - h - 18, x, 140 - h + 18, "s-ink", 1.5),
                line(x - 8, 140 - h - 18, x + 8, 140 - h - 18, "s-ink", 1.5),
            ]
        return "".join(out)

    def pval(ox: float) -> str:
        def sc(v: float) -> float:
            return ox + 150 + v * 9

        return "".join(
            [
                rect(sc(-5), 50, sc(5) - sc(-5), 40, "f-band"),
                line(sc(0), 40, sc(0), 100, "s-muted"),
                line(sc(-12), 70, sc(10), 70, "s-unsure", 5, stroke_linecap="round"),
                circle(sc(-1), 70, 5, "f-plate s-unsure", stroke_width=2.5),
                verdict_text("unsure", ox + 52, 128, 12, "CI −12 % … +10 % is Inconclusive"),
            ]
        )

    cards = [
        (
            "Radar chart",
            "The area grows with the square of each value and depends on the axis order. Lower is better on some axes and higher on others, so one polygon mixes directions.",
            radar,
        ),
        (
            "Bar of means with error bars",
            "A bar hides n and the shape of the data, and readers take the bar's end as a hard edge. The estimation plot (G3) shows every sample instead.",
            bars,
        ),
        (
            "“p > 0.05, unchanged”",
            "A test that fails to reject says the data cannot tell. Only an equivalence test (90 % CI inside ±Δ) can say “no change”.",
            pval,
        ),
    ]
    for i, (title, why, draw) in enumerate(cards):
        ox = 10 + i * 300
        cross = el("path", d=f"M{ox + 6} 171l9 9m0 -9l-9 9", cls="s-tworse", stroke_width=2.2)
        pl.add(draw(ox), cross, text(ox + 22, 180, title, "f-tworse b", 13.5))
        for j, ln in enumerate(_wrap(why, 44)):
            pl.add(text(ox + 6, 202 + j * 17, ln, "f-ink2", 12))
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


def main() -> None:
    # The plates draw from one RNG stream in page order, like the HTML design page.
    for name, make in PLATES.items():
        (OUT / name).write_text(make().render(), encoding="utf-8")
        sys.stdout.write(f"wrote {name}\n")


if __name__ == "__main__":
    main()
