"""Auto-generated example: 2 Float, 0 Categorical (with repeats)."""

import random
import math

import bencher as bn


class CompressionBench(bn.ParametrizedSweep):
    """Measures compression ratio across block size and input entropy."""

    block_size = bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")

    ratio = bn.ResultFloat(units="x", doc="Compression ratio")

    def benchmark(self):
        self.ratio = (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))
        self.ratio += random.gauss(0, 0.15 * 0.3)


def example_sweep_2_float_0_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """2 Float, 0 Categorical (with repeats)."""
    bench = CompressionBench().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["block_size", "entropy"],
        result_vars=["ratio"],
        description="A 2 float + 0 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. A 2D float sweep produces a heatmap. Additional categorical variables create faceted heatmaps, one per category combination.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_2_float_0_cat_with_repeats, level=4, repeats=3)
