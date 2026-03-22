"""Auto-generated example: 2 Float, 2 Categorical (over time)."""

from typing import Any

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class CompressionSuite(bn.ParametrizedSweep):
    """Compression suite: block size, entropy, codec, and level."""

    block_size = bn.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")
    codec = bn.StringSweep(["zlib", "lz4", "zstd"], doc="Compression codec")
    effort = bn.StringSweep(["fast", "balanced", "max"], doc="Compression effort")

    ratio = bn.ResultVar(units="x", doc="Compression ratio")

    _time_offset = 0.0

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
        self.ratio += random.gauss(0, 0.1 * 0.3)
        self.ratio += self._time_offset * 10
        return super().__call__()


def example_sweep_2_float_2_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """2 Float, 2 Categorical (over time)."""
    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.over_time = True
    benchable = CompressionSuite()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["block_size", "entropy", "codec", "effort"],
            result_vars=["ratio"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_2_float_2_cat_over_time, level=4)
