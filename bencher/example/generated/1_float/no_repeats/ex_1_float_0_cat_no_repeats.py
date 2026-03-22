"""Auto-generated example: 1 Float, 0 Categorical (no repeats)."""

from typing import Any

import math

import bencher as bn


class SortBenchmark(bn.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001
        return super().__call__()


def example_1_float_0_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 0 Categorical (no repeats)."""
    bench = SortBenchmark().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bn.run(example_1_float_0_cat_no_repeats, level=4)
