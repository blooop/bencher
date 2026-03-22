"""Auto-generated example: Optimise 1 objective(s), 2D input."""

from typing import Any

import math
import random

import bencher as bn


class ServerOptimizer(bn.ParametrizedSweep):
    """Optimizes server configuration for performance vs cost tradeoff."""

    cpu_cores = bn.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")
    memory_gb = bn.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")

    performance = bn.ResultVar("score", bn.OptDir.maximize, doc="Performance score (maximize)")
    cost = bn.ResultVar("$/hr", bn.OptDir.minimize, doc="Hourly cost (minimize)")

    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10
        self.cost = 0.05 * self.cpu_cores + 0.02 * self.memory_gb
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale * 5)
            self.cost += random.gauss(0, self.noise_scale * 0.1)
        return super().__call__()


def example_optimise_1_objective_2d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Optimise 1 objective(s), 2D input."""
    bench = ServerOptimizer().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["cpu_cores", "memory_gb"],
        result_vars=["performance"],
        const_vars=dict(noise_scale=0.1),
        description="Single-objective optimization over 2D input space using Optuna. The optimizer searches for the parameter combination that maximizes performance.",
        post_description="The Optuna importance plot shows which input parameters most affect the objective.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_optimise_1_objective_2d, level=2, repeats=3, optimise=30)
