"""Auto-generated example: 1 Float, 2 Categorical."""

from typing import Any

import bencher as bch
import math


class SortAnalysis(bch.ParametrizedSweep):
    """Sort analysis across size, algorithm, and data distribution."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bch.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bch.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        dist_factor = {"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}[self.distribution]
        self.time = (
            algo_factor * dist_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        )
        self.time += __import__("random").gauss(0, 0.15 * self.time)
        return super().__call__()


def example_with_repeats_1_float_2_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 2 Categorical."""
    bench = SortAnalysis().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["array_size", "algorithm", "distribution"], result_vars=["time"])

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_1_float_2_cat, level=4, repeats=10)
