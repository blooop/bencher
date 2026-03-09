"""Auto-generated example: Bool Plot: Line."""

from typing import Any

import bencher as bch

import math


class HealthCheckFloat(bch.ParametrizedSweep):
    """Check if service health exceeds a threshold."""

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.load)
        self.healthy = score > 0.5
        return super().__call__()


def example_bool_plot_line(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Line."""
    bench = HealthCheckFloat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["load"], result_vars=["healthy"])
    bench.report.append(res.to_line())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_line, level=3)
