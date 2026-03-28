"""Dimensional extrusion: build shapes by sweeping lower-dimensional forms.

A point → line → grid → set-of-grids → set-of-sets-of-grids, etc.

Each function returns a VGroup representing the shape at that dimensionality.
"""

from __future__ import annotations

from manim import DOWN, RIGHT, VGroup

from bencher.results.manim_cartesian.visual_elements import build_cell

# For 3D+ we arrange copies with a spatial offset to suggest depth
DEPTH_SHIFT_RIGHT = 0.6
DEPTH_SHIFT_UP = 0.3
GROUP_SPACING = 0.8

GAP = "..."


def build_point(cell_size: float) -> VGroup:
    """0-D: a single cell."""
    return VGroup(build_cell(cell_size))


def build_line(n: int, cell_size: float, buff: float = 0.05) -> VGroup:
    """1-D: a horizontal row of n cells."""
    return VGroup(*[build_cell(cell_size) for _ in range(n)]).arrange(RIGHT, buff=buff)


def build_grid(rows: int, cols: int, cell_size: float, buff: float = 0.05) -> VGroup:
    """2-D: a rows x cols grid."""
    grid_rows = []
    for _ in range(rows):
        row = VGroup(*[build_cell(cell_size) for _ in range(cols)]).arrange(RIGHT, buff=buff)
        grid_rows.append(row)
    return VGroup(*grid_rows).arrange(DOWN, buff=buff)


def build_stacked_grids(
    n_stacks: int, rows: int, cols: int, cell_size: float, buff: float = 0.05
) -> VGroup:
    """3-D: n_stacks copies of a grid, offset to suggest depth."""
    from manim import UP

    grids = []
    for i in range(n_stacks):
        g = build_grid(rows, cols, cell_size, buff)
        g.shift(i * DEPTH_SHIFT_RIGHT * RIGHT + i * DEPTH_SHIFT_UP * UP)
        # Fade slightly for depth cue
        g.set_opacity(1.0 - i * 0.08)
        grids.append(g)
    # Reverse so front grid is on top (drawn last)
    grids.reverse()
    return VGroup(*grids)


def build_grouped(n_groups: int, inner_builder, cell_size: float, **inner_kwargs) -> VGroup:
    """4-D+: n_groups copies of the inner shape, arranged in a row."""
    groups = []
    for _ in range(n_groups):
        g = inner_builder(cell_size=cell_size, **inner_kwargs)
        groups.append(g)
    return VGroup(*groups).arrange(RIGHT, buff=GROUP_SPACING)
