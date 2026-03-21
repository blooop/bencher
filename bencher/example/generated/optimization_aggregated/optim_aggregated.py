"""Auto-generated example: Aggregated Optimization."""

from typing import Any

import math
import random

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


def example_optim_aggregated(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Aggregated Optimization."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.use_optuna = True
    bench = AlgorithmBench().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["algorithm", "learning_rate"],
        result_vars=["loss"],
        description="Finds the best learning rate averaged across algorithms. algorithm has optimize=False so Optuna only suggests learning_rate and averages loss over all algorithm choices.",
        post_description="The importance plot shows learning_rate and repeat — algorithm is aggregated away. Compare 'With Repeats' vs 'Without Repeats' to see if measurement noise affects the result.",
    )
    bench.report.append(res.to_optuna_plots())

    return bench


if __name__ == "__main__":
    bch.run(example_optim_aggregated, level=3, repeats=3)
