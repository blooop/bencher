"""Auto-generated example: Bool Plot: Curve."""

import math
import random

import bencher as bn


class HealthCheckFloatNoisy(bn.ParametrizedSweep):
    """Check health with noise — repeated runs produce different outcomes."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bn.ResultBool(doc="Whether the service is healthy")

    def benchmark(self):
        probability = math.sin(math.pi * self.load)
        self.healthy = random.random() < probability


def example_bool_plot_curve(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Bool Plot: Curve."""
    bench = HealthCheckFloatNoisy().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["load"], result_vars=["healthy"])
    bench.report.append(res.to_curve())

    return bench


if __name__ == "__main__":
    bn.run(example_bool_plot_curve, level=3, repeats=20)
