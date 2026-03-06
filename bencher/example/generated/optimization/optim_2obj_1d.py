"""Auto-generated example: Optimization: 2 objective(s), 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_2obj_1d(run_cfg=None):
    """Optimization: 2 objective(s), 1D input."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = BenchableMultiObjective().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["x"], result_vars=["performance", "cost"], const_vars=dict(noise_scale=0.1)
    )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optim_2obj_1d, level=3, repeats=3)
