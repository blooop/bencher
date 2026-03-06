"""Single-Objective 2D Optimization — Maximize performance over a 2D design space.

Extends the 1D case by adding a second design parameter (y).  Optuna
must now navigate a 2-dimensional landscape to find the peak of
'performance'.  The contour / slice plots show how each parameter
contributes to the objective.

Concepts demonstrated:
  - Multi-parameter search spaces
  - 2D contour and slice visualizations
"""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_1obj_2d(run_cfg=None):
    """Maximize performance by sweeping parameters x and y.

    Uses Optuna to navigate a 2D design space and find the
    (x, y) combination that maximises 'performance'."""
    # Enable Optuna-backed optimization instead of pure grid sweep
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = BenchableMultiObjective().to_bench(run_cfg)
    # Sweep the design space with Gaussian noise to simulate variability
    res = bench.plot_sweep(
        input_vars=["x", "y"], result_vars=["performance"], const_vars=dict(noise_scale=0.1)
    )
    # Generate Optuna plots (parameter importance, optimization history)
    res.to_optuna_plots()

    return bench


if __name__ == "__main__":
    bch.run(example_optim_1obj_2d, level=2, repeats=3)
