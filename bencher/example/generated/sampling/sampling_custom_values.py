"""Auto-generated example: Sampling: Custom Values."""

from typing import Any

import math
import bencher as bn


class CustomSampler(bn.ParametrizedSweep):
    """Demonstrates custom sample value selection."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)
        return super().__call__()


def example_sampling_custom_values(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sampling: Custom Values."""
    bench = CustomSampler().to_bench(run_cfg)

    # There are several equivalent ways to specify custom sample values:
    #   1. bn.sweep('load', [0.0, 0.3, 0.7, 1.0])  -- shorthand helper
    #   2. CustomSampler.param.load.with_sample_values([0.0, 0.3, 0.7, 1.0])
    #   3. bn.sweep('load', samples=5)  -- override the number of uniform samples

    # Explicit sample values
    bench.plot_sweep(
        title="Custom Sample Values with bn.sweep()",
        input_vars=[bn.sweep("load", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],
        result_vars=["latency"],
        description="Custom sample values let you pick exact points to evaluate instead of a uniform sweep. Use bn.sweep('name', [values]) as shorthand, or Cls.param.name.with_sample_values([values]) for the explicit form. You can also use bn.sweep('name', samples=N) to override the number of uniform samples without listing values.",
        post_description="The plot shows the function evaluated only at the six hand-picked load values. Compare with the uniform sampling example to see the difference in coverage.",
    )

    # Override number of uniform samples
    bench.plot_sweep(
        title="Override Uniform Sample Count with bn.sweep()",
        input_vars=[bn.sweep("load", samples=5)],
        result_vars=["latency"],
        description="bn.sweep('load', samples=5) overrides how many uniformly-spaced samples are taken from the variable's bounds, without listing explicit values.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sampling_custom_values, level=3)
