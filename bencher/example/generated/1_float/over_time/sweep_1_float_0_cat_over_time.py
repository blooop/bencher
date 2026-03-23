"""Auto-generated example: 1 Float, 0 Categorical (over time)."""

from typing import Any

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class SortBenchmark(bn.ParametrizedSweep):
    """Measures sort duration across array sizes."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.time = self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.1 * self.time)
        self.time += self._time_offset * 10
        return super().__call__()


def example_sweep_1_float_0_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 0 Categorical (over time)."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
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
            description="A 1 float + 0 categorical parameter sweep tracked over time. Setting over_time=True records multiple time snapshots that can be scrubbed via a slider. Each call to plot_sweep with a new time_src appends a snapshot to the history. This is designed for nightly benchmarks or CI pipelines where you want to track how metrics evolve across commits, releases, or environmental changes. Use clear_history=True on the first snapshot to reset, and clear_cache=True to force re-evaluation. A 1D float sweep produces a line plot -- the simplest way to characterise a continuous input.",
            post_description="The time slider lets you scrub through snapshots. The 'All Time Points (aggregated)' tab pools all snapshots into one view, smoothing out per-snapshot noise to reveal long-term trends.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_0_cat_over_time, level=4)
