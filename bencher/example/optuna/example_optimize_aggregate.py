"""Aggregated optimization example.

Demonstrates the sweep-then-optimize workflow with aggregation:
  1. ``plot_sweep`` with ``aggregate=["seed"]`` to visualise mean loss
  2. ``optimize`` with the same aggregation so Optuna sees mean loss
  3. ``optimize`` with ``repeats`` for stochastic/boolean outcomes
"""

import random

import bencher as bn


class NoisySphereWithSeed(bn.ParametrizedSweep):
    """Sphere function with a seed dimension and stochastic noise."""

    x = bn.FloatSweep(default=0, bounds=[-5, 5], samples=10)
    y = bn.FloatSweep(default=0, bounds=[-5, 5], samples=10)
    seed = bn.IntSweep(default=0, bounds=[0, 4], samples=5)

    loss = bn.ResultFloat("ul", bn.OptDir.minimize)

    def benchmark(self):
        random.seed(self.seed)
        noise = random.gauss(0, 0.5)
        self.loss = float(self.x**2 + self.y**2 + noise)


def example_optimize_aggregate(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sweep with aggregation, then optimize with the same aggregation."""
    cfg = NoisySphereWithSeed()
    bench = bn.Bench("OptimizeAggregateExample", cfg, run_cfg=run_cfg)

    # --- 1. Sweep with aggregation over seed -----------------------------
    bench.plot_sweep(
        title="Grid sweep (mean over seed)",
        input_vars=["x", "y", "seed"],
        result_vars=["loss"],
        aggregate=["seed"],
        agg_fn="mean",
        run_cfg=run_cfg,
    )

    # --- 2. Optimize with same aggregation (warm-starts from sweep cache) -
    result = bench.optimize(
        n_trials=30,
        aggregate=["seed"],
        agg_fn="mean",
        title="Optimize (aggregate over seed)",
    )
    bench.report.append_markdown(
        f"### Optimize (aggregate over seed)\n"
        f"Best value (mean over seeds): {result.best_value:.4f}  \n"
        f"Best params: {result.best_params}\n\n"
        f"Optuna only tunes x and y; seed is looped internally and "
        f"the mean loss across all 5 seeds is reported to Optuna."
    )

    # --- 3. Optimize with repeats ----------------------------------------
    result2 = bench.optimize(
        n_trials=20,
        aggregate=["seed"],
        repeats=3,
        agg_fn="mean",
        title="Optimize (aggregate seed + 3 repeats)",
    )
    bench.report.append_markdown(
        f"### Optimize (aggregate + repeats)\n"
        f"Best value: {result2.best_value:.4f}  \n"
        f"Best params: {result2.best_params}\n\n"
        f"Each trial evaluates 5 seeds × 3 repeats = 15 function calls, "
        f"then returns the mean loss to Optuna."
    )

    return bench


if __name__ == "__main__":
    bn.run(example_optimize_aggregate)
