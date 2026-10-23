"""Cartesian product animation for bencher sweep visualisation.

Draws the animation as one self-contained animated SVG (vector frames + SMIL).
The package name is historical: there is no manim dependency.
"""

from bencher.results.manim_cartesian.cartesian_product_cfg import (
    CartesianProductCfg,
    SweepVar,
    from_bench_cfg,
)
from bencher.results.manim_cartesian.cartesian_product_scene import (
    render_animation,
)

__all__ = [
    "CartesianProductCfg",
    "SweepVar",
    "from_bench_cfg",
    "render_animation",
]
