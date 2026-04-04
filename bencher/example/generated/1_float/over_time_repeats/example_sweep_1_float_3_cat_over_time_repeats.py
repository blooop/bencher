"""Auto-generated example: 1 Float, 3 Categorical (over time repeats)."""

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class SortFullMatrix(bn.ParametrizedSweep):
    """Full sort matrix: size, algorithm, distribution, and order."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bn.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")
    stability = bn.StringSweep(["stable", "unstable"], doc="Sort stability")

    time = bn.ResultFloat(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def benchmark(self):
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        dist_factor = {"uniform": 1.0, "sorted": 0.6, "reversed": 1.8}[self.distribution]
        stab_factor = {"stable": 1.1, "unstable": 1.0}[self.stability]
        self.time = (
            algo_factor
            * dist_factor
            * stab_factor
            * self.array_size
            * math.log2(self.array_size + 1)
            * 0.001
        )
        self.time += random.gauss(0, 0.15 * self.time)
        self.time += self._time_offset * 10


def example_sweep_1_float_3_cat_over_time_repeats(
    run_cfg: bn.BenchRunCfg | None = None,
) -> bn.Bench:
    """1 Float, 3 Categorical (over time repeats)."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)
    benchable = SortFullMatrix()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["array_size", "algorithm", "distribution", "stability"],
            result_vars=["time"],
            description="A 1 float + 3 categorical parameter sweep with both repeats and over_time tracking. This combination is the most informative: repeats reveal per-measurement noise at each time point, while over_time captures long-term drift. If your nightly benchmark shows increasing variance, repeats help distinguish whether the algorithm became noisier or the environment became less stable. Adding categorical variables to a float sweep creates faceted line plots -- one curve per category, making it easy to compare how each setting modifies the continuous relationship.",
            post_description="Compare the per-snapshot distributions (via the slider) with the aggregated view. Growing spread over time suggests a real change, not just noise.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_1_float_3_cat_over_time_repeats, level=4, over_time=True)
