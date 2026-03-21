"""Auto-generated example: Optimise Over Time: 1D input."""

from typing import Any

import math
import random
from datetime import datetime, timedelta

import bencher as bch


class ServerOptimizer(bch.ParametrizedSweep):
    """Optimizes server config — performance drifts over time."""

    cpu_cores = bch.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")
    memory_gb = bch.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")

    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance score")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    _drift = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10
        self.performance *= 1.0 - self._drift * 0.15  # degrade over time
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale * 5)
        return super().__call__()


def example_optimise_over_time_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Optimise Over Time: 1D input."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
    benchable = ServerOptimizer()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i in range(4):
        benchable._drift = float(i)
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["cpu_cores"],
            result_vars=["performance"],
            const_vars=dict(noise_scale=0.15),
            description="Optimization over 1D input space with temporal drift. Performance degrades over successive runs. The importance analysis shows repeat, over_time, and input parameters — revealing whether noise or temporal drift dominates.",
            post_description="Check the 'Parameter Importance With Repeats' plot: if over_time has high importance, results are drifting. If repeat is high, measurements are noisy.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optimise_over_time_1d, level=2)
