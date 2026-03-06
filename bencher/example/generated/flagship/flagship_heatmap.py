"""Auto-generated example: Heatmap — Inline Class Definition."""

import math
import bencher as bch


class TerrainSampler(bch.ParametrizedSweep):
    """Samples elevation across a 2D terrain grid.

    Two float inputs are swept to produce a 2D heatmap. The underlying
    function uses sine/cosine to create an interesting terrain pattern.
    """

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="East-west position")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="North-south position")

    elevation = bch.ResultVar(units="m", doc="Terrain elevation at (x, y)")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.elevation = math.sin(2 * math.pi * self.x) * math.cos(
            2 * math.pi * self.y
        ) + 0.5 * math.sin(4 * math.pi * self.x * self.y)
        return super().__call__()


def example_flagship_heatmap(run_cfg=None):
    """Heatmap — Inline Class Definition."""
    bench = TerrainSampler().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "y"],
        result_vars=["elevation"],
        description="Sweep two float variables to produce a 2D heatmap. "
        "The Cartesian product of x and y values is evaluated, and elevation "
        "is color-coded on a grid.",
        post_description="Notice the interference pattern created by the sine/cosine "
        "interaction. Increase the level parameter for finer resolution.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_flagship_heatmap, level=3)
