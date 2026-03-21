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
    bench.plot_sweep(
        input_vars=[bn.p("load", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],
        result_vars=["latency"],
        description="Custom sample values let you pick exact points to evaluate. Use bn.p() to override a variable's sweep values.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sampling_custom_values, level=3)
