"""Auto-generated example: Statistics: 1 repeat(s), 1D float."""

import bencher as bch
import math


class NoisyTimer(bch.ParametrizedSweep):
    """Simulates request timing with configurable measurement noise."""

    endpoint = bch.StringSweep(["api/users", "api/orders", "api/search"], doc="API endpoint")
    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load factor")

    latency = bch.ResultVar(units="ms", doc="Request latency")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Measurement noise")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"api/users": 45, "api/orders": 80, "api/search": 120}[self.endpoint]
        self.latency = base * (1 + 2 * self.load) + 5 * math.sin(math.pi * self.load * 3)
        if self.noise_scale > 0:
            self.latency += __import__("random").gauss(0, self.noise_scale * base * 0.3)
        return super().__call__()


def example_stats_1d_float_repeats_1(run_cfg=None):
    """Statistics: 1 repeat(s), 1D float."""
    bench = NoisyTimer().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["load"], result_vars=["latency"])

    return bench


if __name__ == "__main__":
    bch.run(example_stats_1d_float_repeats_1, level=3)
