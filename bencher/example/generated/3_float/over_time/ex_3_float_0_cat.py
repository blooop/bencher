"""Auto-generated example: 3 Float, 0 Categorical."""

from typing import Any

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class HashBenchmark(bn.ParametrizedSweep):
    """Hash throughput across key size, payload size, and iterations."""

    key_size = bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")

    throughput = bn.ResultVar(units="MB/s", doc="Hash throughput")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.throughput = (
            500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        self.throughput += random.gauss(0, 0.1 * 30)
        self.throughput += self._time_offset * 10
        return super().__call__()


def example_over_time_3_float_0_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """3 Float, 0 Categorical."""
    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.over_time = True
    benchable = HashBenchmark()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["key_size", "payload_size", "iterations"],
            result_vars=["throughput"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_over_time_3_float_0_cat, level=4)
