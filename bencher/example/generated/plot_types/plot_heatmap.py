"""Auto-generated example: Plot Type: Heatmap."""

import bencher as bch

import math


class HeatmapDemo(bch.ParametrizedSweep):
    """2D heatmap of a trigonometric surface."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Surface height")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        return super().__call__()


def example_plot_heatmap(run_cfg=None):
    """Plot Type: Heatmap."""
    bench = HeatmapDemo().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["distance"])
    bench.report.append(res.to_heatmap())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_heatmap, level=2)
