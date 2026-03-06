"""Auto-generated example: 1 Float, 1 Categorical."""

from typing import Any

import bencher as bch
import math


class SortComparison(bch.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bch.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        return super().__call__()


def example_no_repeats_1_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 1 Categorical."""
    bench = SortComparison().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size", "algorithm"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_1_float_1_cat, level=4)
