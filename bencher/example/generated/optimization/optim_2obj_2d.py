"""Auto-generated example: Optimization: 2 objective(s), 2D input."""

import bencher as bch
import math
import random


class ServerOptimizer(bch.ParametrizedSweep):
    """Optimizes server configuration for performance vs cost tradeoff."""

    cpu_cores = bch.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")
    memory_gb = bch.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")

    performance = bch.ResultVar("score", bch.OptDir.maximize, doc="Performance score (maximize)")
    cost = bch.ResultVar("$/hr", bch.OptDir.minimize, doc="Hourly cost (minimize)")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10
        self.cost = 0.05 * self.cpu_cores + 0.02 * self.memory_gb
        if self.noise_scale > 0:
            self.performance += random.gauss(0, self.noise_scale * 5)
            self.cost += random.gauss(0, self.noise_scale * 0.1)
        return super().__call__()


def example_optim_2obj_2d(run_cfg=None):
    """Optimization: 2 objective(s), 2D input."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = ServerOptimizer().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["cpu_cores", "memory_gb"],
        result_vars=["performance", "cost"],
        const_vars=dict(noise_scale=0.1),
        description="Multi-objective optimization over 2D input space using Optuna. The optimizer finds the Pareto front trading off performance vs cost.",
        post_description="The Pareto front shows optimal trade-offs — no point can improve one objective without worsening the other.",
    )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optim_2obj_2d, level=2, repeats=3)
