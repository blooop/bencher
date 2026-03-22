"""Auto-generated example: Plot Type: Heatmap."""

from typing import Any

import bencher as bn

import math


class HeatmapDemo(bn.ParametrizedSweep):
    """2D heatmap of a trigonometric surface."""

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultVar("m", doc="Surface height")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        return super().__call__()


def example_plot_heatmap(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Heatmap."""
    bench = HeatmapDemo().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["distance"])
    bench.report.append(res.to_heatmap())

    return bench


if __name__ == "__main__":
    bn.run(example_plot_heatmap, level=2)
