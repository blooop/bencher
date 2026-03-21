"""Auto-generated example: Bool Plot: Line."""

from typing import Any

import math

import bencher as bn


class HealthCheckFloat(bn.ParametrizedSweep):
    """Check if service health exceeds a threshold."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bn.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.load)
        self.healthy = score > 0.5
        return super().__call__()


def example_bool_plot_line(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Bool Plot: Line."""
    bench = HealthCheckFloat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["load"], result_vars=["healthy"])
    bench.report.append(res.to_line())

    return bench


if __name__ == "__main__":
    bn.run(example_bool_plot_line, level=3)
