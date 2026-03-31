"""Auto-generated example: 1 Float, 1 Categorical (no repeats)."""

import math

import bencher as bn


class SortComparison(bn.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def benchmark(self):
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001


def example_sweep_1_float_1_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 1 Categorical (no repeats)."""
    bench = SortComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size", "algorithm"],
        result_vars=["time"],
        description="A 1 float + 1 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. Adding categorical variables to a float sweep creates faceted line plots -- one curve per category, making it easy to compare how each setting modifies the continuous relationship.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_1_cat_no_repeats, level=4)
