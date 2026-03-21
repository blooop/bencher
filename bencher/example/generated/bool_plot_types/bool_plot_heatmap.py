"""Auto-generated example: Bool Plot: Heatmap."""

from typing import Any

import math
import random

import bencher as bn


class HealthCheck2DNoisy(bn.ParametrizedSweep):
    """2D health check with noise for repeated-run surface plots."""

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bn.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        probability = 0.5 + 0.4 * math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        self.healthy = random.random() < probability
        return super().__call__()


def example_bool_plot_heatmap(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Bool Plot: Heatmap."""
    bench = HealthCheck2DNoisy().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["healthy"])
    bench.report.append(res.to_heatmap())

    return bench


if __name__ == "__main__":
    bn.run(example_bool_plot_heatmap, level=2, repeats=10)
