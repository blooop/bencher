"""Auto-generated example: Sampling: Int Vs Float."""

from typing import Any

import math

import bencher as bn


class IntFloatCompare(bn.ParametrizedSweep):
    """Compares integer vs float sweep behaviour."""

    int_input = bn.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bn.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bn.ResultVar("ul", doc="Computed output")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)
        return super().__call__()


def example_sampling_int_vs_float(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sampling: Int Vs Float."""
    bench = IntFloatCompare().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["int_input", "float_input"],
        result_vars=["output"],
        description=(
            "Integer sweeps produce discrete steps while float sweeps produce continuous "
            "curves. Compare how the plot changes between the two types."
        ),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sampling_int_vs_float, level=3)
