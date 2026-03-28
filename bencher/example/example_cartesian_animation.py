"""Demonstrates the Cartesian product animation.

Shows how each dimension builds on the last:
    point --dim1--> line --dim2--> grid --dim3--> stack
    --repeat--> echo --over_time--> timeline
    --dim4+--> sets of sets ...

Uses PIL to render a GIF — no manim dependency.
Run with: pixi run python bencher/example/example_cartesian_animation.py
Enable logging with: LOGLEVEL=INFO pixi run python ...
"""

from __future__ import annotations

import logging
import sys

from bencher.results.manim_cartesian import CartesianProductCfg, SweepVar, render_animation

logging.basicConfig(level=getattr(logging, "INFO"), stream=sys.stdout)


def example_cartesian_2d_with_meta():
    """2-D sweep + repeat=1 + over_time=1: shows meta dims even when single-element."""
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("x", [0.0, 0.5, 1.0]),
            SweepVar("y", ["A", "B"]),
            SweepVar("repeat", [1]),
            SweepVar("over_time", ["t0"]),
        ],
        result_names=["result"],
    )
    path = render_animation(cfg)
    print(f"2-D + meta GIF: {path}")


def example_cartesian_3d():
    """3-D sweep: two spatial + repeat×2 → 3×2×2 = 12 cells."""
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("theta", [0.0, 1.57, 3.14]),
            SweepVar("phi", [0, 1]),
            SweepVar("repeat", [1, 2]),
        ],
        result_names=["out_sin", "out_cos"],
    )
    path = render_animation(cfg)
    print(f"3-D GIF: {path}")


def example_cartesian_3d_stack():
    """3 spatial dims: shows h→v→stack progression."""
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("x", [0, 1, 2]),
            SweepVar("y", [0, 1, 2]),
            SweepVar("z", [0, 1, 2]),
            SweepVar("repeat", [1]),
        ],
        result_names=["metric"],
    )
    path = render_animation(cfg)
    print(f"3-D stack GIF: {path}")


def example_cartesian_4d():
    """4-D sweep: three spatial + repeat → 2×2×3×2 = 24 cells."""
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("x", [0, 1]),
            SweepVar("y", [0, 1]),
            SweepVar("z", ["A", "B", "C"]),
            SweepVar("repeat", [1, 2]),
        ],
        result_names=["metric"],
    )
    path = render_animation(cfg)
    print(f"4-D GIF: {path}")


def example_cartesian_full():
    """Full demo: 3 spatial + repeat×3 + over_time×3."""
    cfg = CartesianProductCfg(
        all_vars=[
            SweepVar("x", [0, 1, 2]),
            SweepVar("y", [0, 1, 2]),
            SweepVar("z", [0, 1]),
            SweepVar("repeat", [1, 2, 3]),
            SweepVar("over_time", ["t0", "t1", "t2"]),
        ],
        result_names=["metric"],
    )
    path = render_animation(cfg)
    print(f"Full GIF: {path}")


if __name__ == "__main__":
    example_cartesian_2d_with_meta()
    example_cartesian_3d()
    example_cartesian_3d_stack()
    example_cartesian_4d()
    example_cartesian_full()
