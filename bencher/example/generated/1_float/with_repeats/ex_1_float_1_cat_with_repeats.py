"""Auto-generated example: 1 Float, 1 Categorical (with repeats)."""

from typing import Any

import random
import math

import bencher as bn


class SortComparison(bn.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.15 * self.time)
        return super().__call__()


def example_1_float_1_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 1 Categorical (with repeats)."""
    bench = SortComparison().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size", "algorithm"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bn.run(example_1_float_1_cat_with_repeats, level=4, repeats=10)
