"""Auto-generated example: 1 Float, 0 Categorical (no repeats)."""

import math

import bencher as bn


class SortBenchmark(bn.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def benchmark(self):
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001


def example_sweep_1_float_0_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 0 Categorical (no repeats)."""
    bench = SortBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size"],
        result_vars=["time"],
        description="A 1 float + 0 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. A 1D float sweep produces a line plot -- the simplest way to characterise a continuous input.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_0_cat_no_repeats, level=4)
