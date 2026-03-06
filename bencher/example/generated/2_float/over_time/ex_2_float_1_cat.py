"""Auto-generated example: 2 Float, 1 Categorical."""

from typing import Any

import math
import bencher as bch
from datetime import datetime, timedelta


class CompressionCodec(bch.ParametrizedSweep):
    """Compression ratio across block size, entropy, and codec."""

    block_size = bch.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")
    codec = bch.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")

    ratio = bch.ResultVar(units="x", doc="Compression ratio")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        codec_eff = {"zlib": 1.0, "lz4": 0.7, "zstd": 1.1}[self.codec]
        self.ratio = (
            codec_eff * (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))
        )
        self.ratio += __import__("random").gauss(0, 0.1 * 0.3)
        self.ratio += self._time_offset * 10
        return super().__call__()


def example_over_time_2_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 1 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    benchable = CompressionCodec()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["block_size", "entropy", "codec"],
            result_vars=["ratio"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_2_float_1_cat, level=4)
