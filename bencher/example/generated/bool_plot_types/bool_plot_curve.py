"""Auto-generated example: Bool Plot: Curve."""

from typing import Any

import math
import random

import bencher as bch


class HealthCheckFloatNoisy(bch.ParametrizedSweep):
    """Check health with noise — repeated runs produce different outcomes."""

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        probability = math.sin(math.pi * self.load)
        self.healthy = random.random() < probability
        return super().__call__()


def example_bool_plot_curve(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Curve."""
    bench = HealthCheckFloatNoisy().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["load"], result_vars=["healthy"])
    bench.report.append(res.to_curve())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_curve, level=3, repeats=5)
