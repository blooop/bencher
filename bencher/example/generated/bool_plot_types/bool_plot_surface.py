"""Auto-generated example: Bool Plot: Surface."""

from typing import Any

import bencher as bch

import math
import random


class HealthCheck2DNoisy(bch.ParametrizedSweep):
    """2D health check with noise for repeated-run surface plots."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        probability = 0.5 + 0.4 * math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        self.healthy = random.random() < probability
        return super().__call__()


def example_bool_plot_surface(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Surface."""
    bench = HealthCheck2DNoisy().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["healthy"])
    bench.report.append(res.to_surface())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_surface, level=2, repeats=2)
