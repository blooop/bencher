"""Auto-generated example: 1 Float, 1 Categorical (with repeats)."""

import random
import math

import bencher as bn


class SortComparison(bn.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bn.ResultFloat(units="ms", doc="Sort duration")

    def benchmark(self):
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.15 * self.time)


def example_sweep_1_float_1_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 1 Categorical (with repeats)."""
    bench = SortComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size", "algorithm"],
        result_vars=["time"],
        description="A 1 float + 1 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. Adding categorical variables to a float sweep creates faceted line plots -- one curve per category, making it easy to compare how each setting modifies the continuous relationship.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_1_cat_with_repeats, level=4, repeats=10)
