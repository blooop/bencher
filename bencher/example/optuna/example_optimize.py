"""First-class optimization API example.

Demonstrates:
  1. Basic single-objective optimization via ``bench.optimize()``
  2. ``to_optimize()`` one-liner on ParametrizedSweep
  3. Sweep-then-optimize (warm-start automatic via shared cache)
"""

import numpy as np

import bencher as bn


class Rastrigin(bn.ParametrizedSweep):
    """A 2-D Rastrigin function — classic optimization benchmark."""

    x = bn.FloatSweep(default=0, bounds=[-5.12, 5.12], samples=10)
    y = bn.FloatSweep(default=0, bounds=[-5.12, 5.12], samples=10)

    loss = bn.ResultVar("ul", bn.OptDir.minimize)

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        A = 10
        self.loss = float(
            A * 2
            + (self.x**2 - A * np.cos(2 * np.pi * self.x))
            + (self.y**2 - A * np.cos(2 * np.pi * self.y))
        )
        return super().__call__(**kwargs)


def example_optimize(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Demonstrate the first-class optimization API."""
    cfg = Rastrigin()
    bench = bn.Bench("OptimizeExample", cfg, run_cfg=run_cfg)

    # --- 1. Direct optimization -----------------------------------------
    result = bench.optimize(n_trials=30, plot=True)
    bench.report.append_markdown(
        f"### Direct optimization\n"
        f"Best value: {result.best_value:.4f}  \n"
        f"Best params: {result.best_params}"
    )

    # --- 2. Sweep then optimize (warm-start from cache) -----------------
    bench.plot_sweep(
        title="Grid sweep",
        input_vars=[cfg.param.x, cfg.param.y],
        result_vars=[cfg.param.loss],
        run_cfg=run_cfg,
    )
    opt2 = bench.optimize(n_trials=20, title="Warm-started optimization")
    bench.report.append_markdown(
        f"### Warm-started optimization\n"
        f"Warm-start trials: {opt2.n_warm_start_trials}  \n"
        f"Best value: {opt2.best_value:.4f}"
    )

    return bench


def example_optimize_one_liner(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """One-liner convenience via ``to_optimize()``."""
    result = Rastrigin().to_optimize(n_trials=50, run_cfg=run_cfg)
    print(result.summary())
    # Return a bench for consistency with the docs generator
    bench = bn.Bench("OptimizeOneLiner", Rastrigin(), run_cfg=run_cfg)
    bench.report.append(result.to_panel())
    return bench


if __name__ == "__main__":
    bn.run(example_optimize)
