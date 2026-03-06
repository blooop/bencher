"""Auto-generated example: Sampling: Int Vs Float."""

import bencher as bch
import math


class IntFloatCompare(bch.ParametrizedSweep):
    """Compares integer vs float sweep behaviour."""

    int_input = bch.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bch.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bch.ResultVar("ul", doc="Computed output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)
        return super().__call__()


def example_sampling_int_vs_float(run_cfg=None):
    """Sampling: Int Vs Float."""
    bench = IntFloatCompare().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["int_input", "float_input"],
        result_vars=["output"],
        description="Integer sweeps produce discrete steps while float sweeps produce continuous curves. Compare how the plot changes between the two types.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_int_vs_float, level=3)
