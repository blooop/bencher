"""Minimal visual elements for the dimensional extrusion animation.

Just cells and colors — no labels, no brackets, no LaTeX.
"""

from __future__ import annotations

from manim import (
    BLUE,
    GREEN,
    WHITE,
    YELLOW,
    Rectangle,
    VGroup,
)

FILL_COLORS = [BLUE, GREEN, YELLOW, "#FF6B6B", "#C084FC", "#FB923C", "#34D399"]

# Dimension sweep directions cycle through these
# RIGHT, DOWN, then "depth" (offset), then grouping
CELL_COLOR = "#4488CC"
CELL_OPACITY = 0.6


def build_cell(size: float = 0.4) -> Rectangle:
    """A single filled cell."""
    r = Rectangle(
        width=size,
        height=size,
        color=WHITE,
        fill_color=CELL_COLOR,
        fill_opacity=CELL_OPACITY,
        stroke_width=1.5,
    )
    return r


def build_cell_group(rows: int, cols: int, size: float = 0.4, buff: float = 0.05) -> VGroup:
    """Build a rows x cols grid of cells."""
    from manim import DOWN, RIGHT

    grid_rows = []
    for _r in range(rows):
        row = VGroup(*[build_cell(size) for _ in range(cols)]).arrange(RIGHT, buff=buff)
        grid_rows.append(row)
    grid = VGroup(*grid_rows).arrange(DOWN, buff=buff)
    return grid
