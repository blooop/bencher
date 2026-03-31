"""Auto-generated example: Plot Type: Curve."""

import bencher as bn

import math
import random


class LatencyNoisyProfile(bn.ParametrizedSweep):
    """Latency with noise as a function of load."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bn.ResultVar("m", doc="Latency distance metric")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.load) + 0.5
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)


def example_plot_curve(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Curve."""
    bench = LatencyNoisyProfile().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["load"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to_curve())

    return bench


if __name__ == "__main__":
    bn.run(example_plot_curve, level=3, repeats=5)
