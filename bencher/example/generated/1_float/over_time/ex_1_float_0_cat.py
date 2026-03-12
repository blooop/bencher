"""Auto-generated example: 1 Float, 0 Categorical."""

from typing import Any

import math
import bencher as bch
import random
from datetime import datetime, timedelta


class SortBenchmark(bch.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.1 * self.time)
        self.time += self._time_offset * 10
        return super().__call__()


def example_over_time_1_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 0 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    benchable = SortBenchmark()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["array_size"],
            result_vars=["time"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_1_float_0_cat, level=4)
