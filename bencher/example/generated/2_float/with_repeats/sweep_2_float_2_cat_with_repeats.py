"""Auto-generated example: 2 Float, 2 Categorical (with repeats)."""

from typing import Any

import random
import math

import bencher as bn


class CompressionSuite(bn.ParametrizedSweep):
    """Compression suite: block size, entropy, codec, and level."""

    block_size = bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")
    codec = bn.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")
    effort = bn.StringSweep(["fast", "balanced", "max"], doc="Compression effort")

    ratio = bn.ResultVar(units="x", doc="Compression ratio")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        codec_eff = {"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}[self.codec]
        effort_mult = {"fast": 0.8, "balanced": 1.0, "max": 1.15}[self.effort]
        self.ratio = (
            codec_eff
            * effort_mult
            * (1.0 - 0.7 * self.entropy)
            * (1.0 + 0.3 * math.log2(self.block_size / 512))
        )
        self.ratio += random.gauss(0, 0.15 * 0.3)
        return super().__call__()


def example_sweep_2_float_2_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """2 Float, 2 Categorical (with repeats)."""
    bench = CompressionSuite().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["block_size", "entropy", "codec", "effort"],
        result_vars=["ratio"],
        description="A 2 float + 2 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. A 2D float sweep produces a heatmap. Additional categorical variables create faceted heatmaps, one per category combination.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_2_float_2_cat_with_repeats, level=4, repeats=3)
