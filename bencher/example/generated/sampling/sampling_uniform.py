"""Auto-generated example: Sampling: Uniform."""

import bencher as bch
import math


class UniformSampler(bch.ParametrizedSweep):
    """Demonstrates uniform sampling across a parameter range."""

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bch.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)
        return super().__call__()


def example_sampling_uniform(run_cfg=None):
    """Sampling: Uniform."""
    bench = UniformSampler().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["load"],
        result_vars=["latency"],
        description="Uniform sampling distributes points evenly across the parameter bounds. The number of samples is controlled by the level parameter.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_uniform, level=4)
