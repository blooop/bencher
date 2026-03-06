"""Auto-generated example: Plot Type: Curve."""

import bencher as bch

import math
import random


class LatencyNoisyProfile(bch.ParametrizedSweep):
    """Latency with noise as a function of load."""

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Latency distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.load) + 0.5
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)
        return super().__call__()


def example_plot_curve(run_cfg=None):
    """Plot Type: Curve."""
    bench = LatencyNoisyProfile().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["load"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to_curve())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_curve, level=3, repeats=5)
