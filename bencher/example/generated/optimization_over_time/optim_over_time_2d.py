"""Auto-generated example: Optimise Over Time: 2D input."""

from typing import Any

import math
import random
from datetime import datetime, timedelta

import bencher as bn


class ServerOptimizer(bn.ParametrizedSweep):
    """Optimizes server config — performance drifts over time."""

    cpu_cores = bn.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")
    memory_gb = bn.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")

    performance = bn.ResultVar("score", bn.OptDir.maximize, doc="Performance score")

    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    _drift = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10
        self.performance *= 1.0 - self._drift * 0.15  # degrade over time
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale * 5)
        return super().__call__()


def example_optim_over_time_2d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Optimise Over Time: 2D input."""
    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
    benchable = ServerOptimizer()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i in range(4):
        benchable._drift = float(i)
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "over_time",
            input_vars=["cpu_cores", "memory_gb"],
            result_vars=["performance"],
            const_vars=dict(noise_scale=0.15),
            description="Optimization over 2D input space with temporal drift. Performance degrades over successive runs. The importance analysis shows repeat, over_time, and input parameters — revealing whether noise or temporal drift dominates.",
            post_description="Check the 'Parameter Importance With Repeats' plot: if over_time has high importance, results are drifting. If repeat is high, measurements are noisy.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_optim_over_time_2d, level=2, optimise=30)
