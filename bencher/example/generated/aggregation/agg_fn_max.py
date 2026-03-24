"""Auto-generated example: Aggregate with Max."""

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
        self.ratio = codec_eff * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))
        self.ratio += random.gauss(0, 0.15 * 0.3)
        return super().__call__()


def example_agg_fn_max(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate with Max."""
    bench = CompressionCodec().to_bench(run_cfg)
    bench.plot_sweep(input_vars=['block_size', 'entropy', 'codec'], result_vars=['ratio'], description='Combine aggregate=["codec"] with agg_fn="max" to show the best-case (maximum) compression ratio across codecs for each (block_size, entropy) combination.', post_description='Unlike the default mean aggregation, agg_fn="max" picks the best codec at every point. Other options: "min", "sum", "median".', aggregate=['codec'], agg_fn='max')

    return bench


if __name__ == "__main__":
    bn.run(example_agg_fn_max, level=4, repeats=3)
