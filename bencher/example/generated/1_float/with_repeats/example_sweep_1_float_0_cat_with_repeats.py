"""Auto-generated example: 1 Float, 0 Categorical (with repeats)."""

import random
import math

import bencher as bn


class SortBenchmark(bn.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bn.ResultFloat(units="ms", doc="Sort duration")

    def benchmark(self):
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.15 * self.time)


def example_sweep_1_float_0_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 0 Categorical (with repeats)."""
    bench = SortBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size"],
        result_vars=["time"],
        description="A 1 float + 0 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. A 1D float sweep produces a line plot -- the simplest way to characterise a continuous input.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_0_cat_with_repeats, level=4, repeats=10)
