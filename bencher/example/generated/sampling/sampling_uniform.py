"""Auto-generated example: Sampling: Uniform."""

import math

import bencher as bn


class UniformSampler(bn.ParametrizedSweep):
    """Demonstrates uniform sampling across a parameter range."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def benchmark(self):
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)


def example_sampling_uniform(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sampling: Uniform."""
    bench = UniformSampler().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["load"],
        result_vars=["latency"],
        description="Uniform sampling distributes points evenly across the parameter bounds. The number of samples is controlled by the level parameter.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sampling_uniform, level=4)
