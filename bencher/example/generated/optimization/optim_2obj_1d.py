"""Auto-generated example: Optimization: 2 objective(s), 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableMultiObjective


def example_optim_2obj_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Optimization: 2 objective(s), 1D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 3
    run_cfg.repeats = 3
    run_cfg.use_optuna = True
    benchable = BenchableMultiObjective()
    benchable.noise_scale = 0.1
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x"], result_vars=["performance", "cost"])
    res.to_optuna_plots()

    return bench


if __name__ == "__main__":
    bch.run(example_optim_2obj_1d)
