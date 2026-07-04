"""Inline-SVG sparklines for benchmark trend series.

A sparkline compresses a metric's over-time :func:`~bencher.report_export.series_for_var`
(per-event mean with a ±std noise band) into a tiny inline SVG, so both the trend
and the run-to-run spread are visible at a glance without opening a full report.
The output is pure numeric geometry — no caller strings are interpolated — so it
is safe to embed unescaped.
"""

from __future__ import annotations

import math
from itertools import zip_longest


def sparkline_svg(
    means: list[float | None],
    stds: list[float | None],
    *,
    width: int = 120,
    height: int = 28,
    pad: int = 3,
) -> str:
    """Return an inline SVG sparkline: ±std band, mean line, a node per run.

    Pure-numeric input (no caller strings interpolated), so the output is safe to
    render unescaped. Auto-scales to the band extent; degenerates gracefully to a
    single node when only one finite point exists, and to an empty ``<svg>`` when
    none do.

    The SVG carries a viewBox and ``preserveAspectRatio="none"`` so CSS can
    stretch it to whatever width its container ends up at. ``vector-effect``
    keeps the line/band stroke crisp under that non-uniform scaling.

    A small node marks every event on the line so the eye can see where the
    individual runs sit; nodes are drawn identically (the latest is simply the
    rightmost) and the sparkline itself stays uncolored — the caller (e.g. a cell
    background) owns any verdict color.

    With more than one point, a narrow right-margin column collapses every run's
    mean onto the (shared) value axis as identical alpha-blended dots, so value
    regions where runs cluster read darker — surfacing the run-to-run spread, and
    any bimodality, that the mean line alone hides.

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

    # With >1 point, a distribution column (one dot per run) hugs the right edge
    # just past the trend, separated by a small gap so the two read as one unit
    # rather than being split by dead space. A lone point has no spread to show,
    # so it keeps the full width and draws no column.
    has_col = len(pts) > 1
    col_gap = 4
    col_x = width - pad - 2
    plot_right = (col_x - col_gap) if has_col else (width - pad)

    def x_of(i: int) -> float:
        return pad + (i / max(n - 1, 1)) * (plot_right - pad)

    def y_of(v: float) -> float:
        return height - pad - ((v - lo) / span) * (height - 2 * pad)

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

    # A small node at each run, all drawn alike (the rightmost is the latest).
    # Kept close to the line's own weight in a slightly darker shade so the
    # individual datapoints are visible without cluttering. A round-cap
    # zero-length line renders a constant-size circle under the non-uniform
    # stretch (a <circle> would squash into an ellipse); vector-effect does not
    # inherit, so it is set per node.
    nodes = "".join(
        f'<line x1="{x_of(i):.1f}" y1="{y_of(m):.1f}" '
        f'x2="{x_of(i):.1f}" y2="{y_of(m):.1f}" '
        'vector-effect="non-scaling-stroke"/>'
        for i, m, _ in pts
    )
    parts.append(f'<g stroke="#334155" stroke-width="2.4" stroke-linecap="round">{nodes}</g>')

    if has_col:
        # Every run's mean collapsed onto the value axis at a fixed x, all dots
        # identical. Faint alpha dots pile up where runs cluster (darker =
        # denser), sharing the sparkline's y-scale so a dot's height means the
        # same value in both. Shared <g> style keeps each dot to coords +
        # non-scaling-stroke (which does not inherit).
        dots = "".join(
            f'<line x1="{col_x:.1f}" y1="{y_of(m):.1f}" '
            f'x2="{col_x:.1f}" y2="{y_of(m):.1f}" '
            'vector-effect="non-scaling-stroke"/>'
            for _, m, _ in pts
        )
        parts.append(
            '<g class="dist" stroke="#64748b" stroke-width="3" '
            f'stroke-opacity="0.32" stroke-linecap="round">{dots}</g>'
        )

    parts.append("</svg>")
    return "".join(parts)
