"""Auto-generated example: 1 Float, 2 Categorical (no repeats)."""

from typing import Any

import math

import bencher as bn


class SortAnalysis(bn.ParametrizedSweep):
    """Sort analysis across size, algorithm, and data distribution."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        dist_factor = {"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}[self.distribution]
        self.time = (
            algo_factor * dist_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        )
        return super().__call__()


def example_1_float_2_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 2 Categorical (no repeats)."""
    bench = SortAnalysis().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size", "algorithm", "distribution"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bn.run(example_1_float_2_cat_no_repeats, level=4)
