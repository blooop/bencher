"""Auto-generated example: 1 Float, 2 Categorical (over time)."""

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class SortAnalysis(bn.ParametrizedSweep):
    """Sort analysis across size, algorithm, and data distribution."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def benchmark(self):
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        dist_factor = {"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}[self.distribution]
        self.time = (
            algo_factor * dist_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        )
        self.time += random.gauss(0, 0.1 * self.time)
        self.time += self._time_offset * 10


def example_sweep_1_float_2_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """1 Float, 2 Categorical (over time)."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = SortAnalysis()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["array_size", "algorithm", "distribution"],
            result_vars=["time"],
            description="A 1 float + 2 categorical parameter sweep tracked over time. Setting over_time=True records multiple time snapshots that can be scrubbed via a slider. Each call to plot_sweep with a new time_src appends a snapshot to the history. This is designed for nightly benchmarks or CI pipelines where you want to track how metrics evolve across commits, releases, or environmental changes. Use clear_history=True on the first snapshot to reset, and clear_cache=True to force re-evaluation. Adding categorical variables to a float sweep creates faceted line plots -- one curve per category, making it easy to compare how each setting modifies the continuous relationship.",
            post_description="The time slider lets you scrub through snapshots. The 'All Time Points (aggregated)' tab pools all snapshots into one view, smoothing out per-snapshot noise to reveal long-term trends.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_2_cat_over_time, level=4, over_time=True)
