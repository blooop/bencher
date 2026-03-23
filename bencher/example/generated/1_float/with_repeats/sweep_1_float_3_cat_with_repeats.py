"""Auto-generated example: 1 Float, 3 Categorical (with repeats)."""

from typing import Any

import random
import math

import bencher as bn


class SortFullMatrix(bn.ParametrizedSweep):
    """Full sort matrix: size, algorithm, distribution, and order."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")
    stability = bn.StringSweep(["stable", "unstable"], doc="Sort stability")

    time = bn.ResultVar(units="ms", doc="Sort duration")

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
        self.time += random.gauss(0, 0.15 * self.time)
        return super().__call__()


def example_sweep_1_float_3_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 3 Categorical (with repeats)."""
    bench = SortFullMatrix().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size", "algorithm", "distribution", "stability"],
        result_vars=["time"],
        description="A 1 float + 3 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. Adding categorical variables to a float sweep creates faceted line plots -- one curve per category, making it easy to compare how each setting modifies the continuous relationship.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_3_cat_with_repeats, level=4, repeats=10)
