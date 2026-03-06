"""Auto-generated example: 1 Float, 3 Categorical."""

import math
import bencher as bch
from datetime import datetime, timedelta


class SortFullMatrix(bch.ParametrizedSweep):
    """Full sort matrix: size, algorithm, distribution, and order."""

    array_size = bch.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bch.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")
    distribution = bch.StringSweep(["uniform", "sorted", "reversed"], doc="Data distribution")
    stability = bch.StringSweep(["stable", "unstable"], doc="Sort stability")

    time = bch.ResultVar(units="ms", doc="Sort duration")

    _time_offset = 0.0

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
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
        self.time += __import__("random").gauss(0, 0.1 * self.time)
        self.time += self._time_offset * 10
        return super().__call__()


def example_over_time_1_float_3_cat(run_cfg=None):
    """1 Float, 3 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
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
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_1_float_3_cat, level=4)
