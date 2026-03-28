"""Cartesian product animation for bencher sweep visualisation.

Uses PIL + moviepy (both already bencher dependencies) for fast
frame-by-frame rendering.  No manim dependency required.
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
