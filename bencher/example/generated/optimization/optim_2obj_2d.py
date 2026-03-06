"""Multi-Objective 2D Optimization — Pareto front over a 2D design space.

The most complex variant: two objectives and two design parameters.
The Pareto front now captures richer trade-offs because both x and y
influence the performance-cost balance in different ways.

Concepts demonstrated:
  - Full multi-objective optimization
  - Pareto front in a higher-dimensional design space
  - Parameter importance across multiple objectives
"""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_2obj_2d(run_cfg=None):
    """Balance performance vs. cost over a 2D design space.

    Full multi-objective optimization with two design
    parameters (x, y) and two competing objectives.  The
    resulting Pareto front shows optimal trade-offs."""
    # Enable Optuna-backed optimization instead of pure grid sweep
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = BenchableMultiObjective().to_bench(run_cfg)
    # Sweep the design space with Gaussian noise to simulate variability
    res = bench.plot_sweep(
        input_vars=["x", "y"], result_vars=["performance", "cost"], const_vars=dict(noise_scale=0.1)
    )
    # Generate Optuna plots (parameter importance, optimization history, Pareto front)
    res.to_optuna_plots()

    return bench


if __name__ == "__main__":
    bch.run(example_optim_2obj_2d, level=2, repeats=3)
