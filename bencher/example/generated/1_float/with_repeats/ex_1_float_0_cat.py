"""Auto-generated example: 1 Float, 0 Categorical."""

import bencher as bch
import math


class SortBenchmark(bch.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += __import__("random").gauss(0, 0.15 * self.time)
        return super().__call__()


def example_with_repeats_1_float_0_cat(run_cfg=None):
    """1 Float, 0 Categorical."""
    bench = SortBenchmark().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_1_float_0_cat, level=4, repeats=10)
