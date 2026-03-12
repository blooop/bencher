"""Auto-generated example: 2 Float, 0 Categorical."""

from typing import Any

import bencher as bch
import math
import random


class CompressionBench(bch.ParametrizedSweep):
    """Measures compression ratio across block size and input entropy."""

    block_size = bch.FloatSweep(default=4096, bounds=[512, 65536], doc="Block size in bytes")
    entropy = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Input data entropy")

    ratio = bch.ResultVar(units="x", doc="Compression ratio")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.ratio = (1.0 - 0.7 * self.entropy) * (1.0 + 0.3 * math.log2(self.block_size / 512))
        self.ratio += random.gauss(0, 0.15 * 0.3)
        return super().__call__()


def example_with_repeats_2_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 0 Categorical."""
    bench = CompressionBench().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["block_size", "entropy"], result_vars=["ratio"])

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_2_float_0_cat, level=4, repeats=3)
