"""Multi-Objective 1D Optimization — Balance performance vs. cost.

Introduces a second objective: 'cost' (minimize) alongside 'performance'
(maximize).  Because the objectives compete — higher x raises both
performance and cost — there is no single best solution.  Instead,
Optuna finds a set of Pareto-optimal trade-offs.

Concepts demonstrated:
  - Competing objectives with different optimization directions
  - Pareto front visualization
"""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_2obj_1d(run_cfg=None):
    """Balance performance (maximize) vs. cost (minimize) over x.

    Demonstrates Pareto optimization: Optuna discovers a set
    of trade-off solutions where improving one objective
    necessarily worsens the other."""
    # Enable Optuna-backed optimization instead of pure grid sweep
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = BenchableMultiObjective().to_bench(run_cfg)
    # Sweep the design space with Gaussian noise to simulate variability
    res = bench.plot_sweep(
        input_vars=["x"], result_vars=["performance", "cost"], const_vars=dict(noise_scale=0.1)
    )
    # Generate Optuna plots (parameter importance, optimization history, Pareto front)
    res.to_optuna_plots()

    return bench


if __name__ == "__main__":
    bch.run(example_optim_2obj_1d, level=3, repeats=3)
