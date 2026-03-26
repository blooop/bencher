"""Auto-generated example: 2 Float, 1 Categorical (no repeats)."""

from typing import Any

import math

import bencher as bn


class CompressionCodec(bn.ParametrizedSweep):
    """Compression ratio across block size, entropy, and codec."""

    block_size = bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")
    codec = bn.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")

    ratio = bn.ResultVar(units="x", doc="Compression ratio")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        codec_eff = {"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}[self.codec]
        self.ratio = (
            codec_eff * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))
        )
        return super().__call__()


def example_sweep_2_float_1_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """2 Float, 1 Categorical (no repeats)."""
    bench = CompressionCodec().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["block_size", "entropy", "codec"],
        result_vars=["ratio"],
        description=(
            "A 2 float + 1 categorical parameter sweep with a single sample per combination. "
            "Bencher calculates the Cartesian product of all input variables and evaluates "
            "the benchmark function at each point. With no repeats, each combination appears "
            "exactly once -- useful for deterministic functions or quick exploration before "
            "committing to longer runs. A 2D float sweep produces a heatmap. Additional "
            "categorical variables create faceted heatmaps, one per category combination."
        ),
        post_description=(
            "Each tab shows a different view of the same data: interactive plots, tabular "
            "summaries, and raw data. Use the tabs to explore the sweep results from "
            "different angles."
        ),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_2_float_1_cat_no_repeats, level=4)
