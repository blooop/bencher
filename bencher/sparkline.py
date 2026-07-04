"""Inline-SVG sparklines for benchmark trend series.

A sparkline compresses a metric's over-time :func:`~bencher.report_export.series_for_var`
(per-event mean with a ±std noise band) into a tiny inline SVG, so run-to-run
noise and the latest movement are visible at a glance without opening a full
report. The output is pure numeric geometry — no caller strings are interpolated
— so it is safe to embed unescaped.
"""

from __future__ import annotations

import math
from itertools import zip_longest

# Neutral latest-point accent when the caller passes no verdict color.
DEFAULT_ACCENT = "#1f2937"
# Previous-event marker: always slate, so only the latest dot carries the accent.
_PREV_STROKE = "#475569"


def sparkline_svg(
    means: list[float | None],
    stds: list[float | None],
    *,
    width: int = 120,
    height: int = 28,
    pad: int = 3,
    accent: str | None = None,
) -> str:
    """Return an inline SVG sparkline: ±std band, mean line, previous + latest dots.

    Pure-numeric input (no caller strings interpolated), so the output is safe to
    render unescaped. Auto-scales to the band extent; degenerates gracefully to a
    single dot when only one finite point exists, and to an empty ``<svg>`` when
    none do.

    The SVG carries a viewBox and ``preserveAspectRatio="none"`` so CSS can
    stretch it to whatever width its container ends up at. ``vector-effect``
    keeps the line/band stroke crisp under that non-uniform scaling.

    Two dots mark the previous and latest events on the line so the eye can see
    precisely where the last comparison sits. The latest dot is drawn in
    ``accent`` (e.g. a verdict color the caller resolved); the previous dot stays
    slate. ``accent`` defaults to a neutral near-black.

    ``means`` is the trend and drives the x-axis; ``stds`` is the noise band and
    is paired positionally. The two are zipped with :func:`itertools.zip_longest`
    so a length mismatch degrades gracefully rather than silently dropping
    trailing points: a missing std collapses that point's band to zero, and a
    surplus std (no matching mean) is ignored.
    """
    pts = [
        (i, m, (s if (s is not None and math.isfinite(s)) else 0.0))
        for i, (m, s) in enumerate(zip_longest(means, stds))
        if m is not None and math.isfinite(m)
    ]
    svg_open = (
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'xmlns="http://www.w3.org/2000/svg">'
    )
    if not pts:
        return f"{svg_open}</svg>"

    n = len(means)
    lo = min(m - s for _, m, s in pts)
    hi = max(m + s for _, m, s in pts)
    span = (hi - lo) or 1.0

    def x_of(i: int) -> float:
        return pad + (i / max(n - 1, 1)) * (width - 2 * pad)

    def y_of(v: float) -> float:
        return height - pad - ((v - lo) / span) * (height - 2 * pad)

    accent_stroke = accent or DEFAULT_ACCENT

    def dot(x: float, y: float, fill: str) -> str:
        # Zero-length line + round cap + non-scaling-stroke renders a true circle
        # at a constant pixel size; a <circle> would squash into an ellipse under
        # the SVG's non-uniform stretch.
        return (
            f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{fill}" stroke-width="6" stroke-linecap="round" '
            f'vector-effect="non-scaling-stroke"/>'
        )

    parts = [svg_open]
    if len(pts) > 1:
        upper = [(x_of(i), y_of(m + s)) for i, m, s in pts]
        lower = [(x_of(i), y_of(m - s)) for i, m, s in reversed(pts)]
        band = " ".join(f"{x:.1f},{y:.1f}" for x, y in upper + lower)
        line = " ".join(f"{x_of(i):.1f},{y_of(m):.1f}" for i, m, _ in pts)
        parts.append(f'<polygon points="{band}" fill="#94a3b8" fill-opacity="0.25"/>')
        parts.append(
            f'<polyline points="{line}" fill="none" stroke="#475569" '
            'stroke-width="1.2" vector-effect="non-scaling-stroke"/>'
        )
        # Previous-event marker on the line so the comparison anchor is visible.
        prev_i, prev_m, _ = pts[-2]
        parts.append(dot(x_of(prev_i), y_of(prev_m), _PREV_STROKE))
    # Latest-event marker, accent-colored.
    last_i, last_m, _ = pts[-1]
    parts.append(dot(x_of(last_i), y_of(last_m), accent_stroke))
    parts.append("</svg>")
    return "".join(parts)
