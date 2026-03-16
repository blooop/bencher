"""Auto-generated example: 2 Float, 2 Categorical."""

from typing import Any

import math

import bencher as bch


class CompressionSuite(bch.ParametrizedSweep):
    """Compression suite: block size, entropy, codec, and level."""

    block_size = bch.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")
    codec = bch.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")
    effort = bch.StringSweep(["fast", "balanced", "max"], doc="Compression effort")

    ratio = bch.ResultVar(units="x", doc="Compression ratio")

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
        return super().__call__()


def example_no_repeats_2_float_2_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 2 Categorical."""
    bench = CompressionSuite().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["block_size", "entropy", "codec", "effort"], result_vars=["ratio"])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_2_float_2_cat, level=4)
