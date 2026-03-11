"""Auto-generated example: Bool Plot: Heatmap."""

from typing import Any

import math

import bencher as bch


class HealthCheck2D(bch.ParametrizedSweep):
    """2D health check based on two float inputs."""

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        self.healthy = score > 0.0
        return super().__call__()


def example_bool_plot_heatmap(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Heatmap."""
    bench = HealthCheck2D().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["healthy"])
    bench.report.append(res.to_heatmap())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_heatmap, level=2)
