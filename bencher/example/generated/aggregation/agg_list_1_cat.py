"""Auto-generated example: Aggregate by Name (list)."""

from typing import Any

import random
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
        self.ratio += random.gauss(0, 0.15 * 0.3)
        return super().__call__()


def example_agg_list_1_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate by Name (list)."""
    bench = CompressionCodec().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["block_size", "entropy", "codec"],
        result_vars=["ratio"],
        description='Aggregate a specific dimension by name using aggregate=["codec"]. The codec categorical is averaged out, leaving a 2D heatmap of block_size vs entropy. This is the most explicit form — you list exactly which dimensions to collapse.',
        post_description="The aggregated view shows a heatmap because two float dimensions remain after collapsing codec. The non-aggregated view below shows the full faceted heatmaps (one per codec).",
        aggregate=["codec"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_list_1_cat, level=4, repeats=3)
