"""Single-Objective 1D Optimization — Maximize performance by tuning one parameter.

The simplest Optuna example: sweep a single design parameter (x) and
let Optuna find the value that maximises 'performance'.  Noise is added
to simulate real-world measurement variability.

Concepts demonstrated:
  - Enabling Optuna via ``run_cfg.use_optuna = True``
  - Parameter importance and optimization history plots
"""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_1obj_1d(run_cfg=None):
    """Maximize performance by sweeping parameter x.

    Uses Optuna to find the x value that maximises the
    'performance' objective with Gaussian noise (scale=0.1)."""
    # Enable Optuna-backed optimization instead of pure grid sweep
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = BenchableMultiObjective().to_bench(run_cfg)
    # Sweep the design space with Gaussian noise to simulate variability
    res = bench.plot_sweep(
        input_vars=["x"], result_vars=["performance"], const_vars=dict(noise_scale=0.1)
    )
    # Generate Optuna plots (parameter importance, optimization history)
    res.to_optuna_plots()

    return bench


if __name__ == "__main__":
    bch.run(example_optim_1obj_1d, level=3, repeats=3)
