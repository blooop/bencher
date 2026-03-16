"""Auto-generated example: 1 Float, 3 Categorical."""

from typing import Any

import math

import bencher as bch


class SortFullMatrix(bch.ParametrizedSweep):
    """Full sort matrix: size, algorithm, distribution, and order."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bch.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bch.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")
    stability = bch.StringSweep(["stable", "unstable"], doc="Sort stability")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        dist_factor = {"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}[self.distribution]
        stab_factor = {"stable": 1.1, "unstable": 1.0}[self.stability]
        self.time = (
            algo_factor
            * dist_factor
            * stab_factor
            * self.array_size
            * math.log2(self.array_size + 1)
            * 0.001
        )
        return super().__call__()


def example_no_repeats_1_float_3_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 3 Categorical."""
    bench = SortFullMatrix().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size", "algorithm", "distribution", "stability"], result_vars=["time"]
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_1_float_3_cat, level=4)
