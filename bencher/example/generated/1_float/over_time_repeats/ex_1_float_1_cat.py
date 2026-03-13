"""Auto-generated example: 1 Float, 1 Categorical."""

from typing import Any

import random
import math
import bencher as bch
from datetime import datetime, timedelta


class SortComparison(bch.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bch.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.15 * self.time)
        self.time += self._time_offset * 10
        return super().__call__()


def example_over_time_repeats_1_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 1 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
    benchable = SortComparison()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["array_size", "algorithm"],
            result_vars=["time"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_repeats_1_float_1_cat, level=4)
