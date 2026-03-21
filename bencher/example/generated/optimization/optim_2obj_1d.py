"""Auto-generated example: Optimization: 2 objective(s), 1D input."""

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


def example_optim_2obj_1d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Optimization: 2 objective(s), 1D input."""
    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = ServerOptimizer().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["cpu_cores"],
        result_vars=["performance", "cost"],
        const_vars=dict(noise_scale=0.1),
        description="Multi-objective optimization over 1D input space using Optuna. The optimizer finds the Pareto front trading off performance vs cost.",
        post_description="The Pareto front shows optimal trade-offs — no point can improve one objective without worsening the other.",
    )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bn.run(example_optim_2obj_1d, level=3, repeats=3)
