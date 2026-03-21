"""Auto-generated example: Aggregated Optimisation (Over Time)."""

from typing import Any

import math
import random
from datetime import datetime, timedelta

import bencher as bch


class AlgorithmBench(bch.ParametrizedSweep):
    """Finds best learning rate across algorithms (aggregated)."""

    algorithm = bch.StringSweep(
        ["gradient_descent", "adam", "rmsprop"],
        doc="Optimization algorithm",
        optimize=False,  # sweep but don't optimize — aggregate results
    )
    learning_rate = bch.FloatSweep(default=0.01, bounds=[0.001, 1.0], doc="Learning rate")

    loss = bch.ResultVar("loss", bch.OptDir.minimize, doc="Training loss (minimize)")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_sensitivity = {"gradient_descent": 1.0, "adam": 0.6, "rmsprop": 0.8}
        optimal_lr = 0.01 * algo_sensitivity[self.algorithm]
        self.loss = (math.log10(self.learning_rate) - math.log10(optimal_lr)) ** 2
        self.loss += random.gauss(0, 0.02)
        return super().__call__()


def example_optimise_aggregated_over_time(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Aggregated Optimisation (Over Time)."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
    benchable = AlgorithmBench()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i in range(3):
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["algorithm", "learning_rate"],
            result_vars=["loss"],
            description="Finds the best learning rate averaged across algorithms, tracked over time. algorithm has optimize=False so Optuna aggregates over it. The importance plot shows learning_rate, repeat, and over_time.",
            post_description="The importance plot reveals which factors matter: the optimized parameter (learning_rate), measurement noise (repeat), or temporal drift (over_time).",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optimise_aggregated_over_time, level=3)
