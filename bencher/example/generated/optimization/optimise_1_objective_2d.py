"""Auto-generated example: Optimise 1 objective(s), 2D input."""

from typing import Any

import math
import random

import bencher as bch


class ServerOptimizer(bch.ParametrizedSweep):
    """Optimizes server configuration for performance vs cost tradeoff."""

    cpu_cores = bch.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")
    memory_gb = bch.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")

    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance score (maximize)")
    cost = bch.ResultVar("$/hr", bch.OptDir.minimize, doc="Hourly cost (minimize)")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10
        self.cost = 0.05 * self.cpu_cores + 0.02 * self.memory_gb
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale * 5)
            self.cost += random.gauss(0, self.noise_scale * 0.1)
        return super().__call__()


def example_optimise_1_objective_2d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Optimise 1 objective(s), 2D input."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = ServerOptimizer().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["cpu_cores", "memory_gb"],
        result_vars=["performance"],
        const_vars=dict(noise_scale=0.1),
        description="Single-objective optimization over 2D input space using Optuna. The optimizer searches for the parameter combination that maximizes performance.",
        post_description="The Optuna importance plot shows which input parameters most affect the objective.",
    )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optimise_1_objective_2d, level=2, repeats=3)
