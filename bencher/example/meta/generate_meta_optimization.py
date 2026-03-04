"""Meta-generator: Optimization & Pareto.

Shows optimization direction, Optuna integration, and multi-objective Pareto.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "optimization"


class MetaOptimization(MetaGeneratorBase):
    """Generate notebooks demonstrating optimization features."""

    n_objectives = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of objectives")
    input_dims = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"optim_{self.n_objectives}obj_{self.input_dims}d"
        title = f"Optimization: {self.n_objectives} objective(s), {self.input_dims}D input"

        if self.n_objectives == 1:
            result_vars_code = '["performance"]'
        else:
            result_vars_code = '["performance", "cost"]'

        if self.input_dims == 1:
            input_vars_code = '["x"]'
        else:
            input_vars_code = '["x", "y"]'

        level = 2 if self.input_dims >= 2 else 3

        setup_code = (
            "import bencher as bch\n"
            "from bencher.example.meta.benchable_objects import BenchableMultiObjective\n"
            "run_cfg = bch.BenchRunCfg()\n"
            f"run_cfg.level = {level}\n"
            "run_cfg.repeats = 3\n"
            "run_cfg.use_optuna = True\n"
            "benchable = BenchableMultiObjective()\n"
            "benchable.noise_scale = 0.1\n"
            "bench = benchable.to_bench(run_cfg)\n"
            f"res = bench.plot_sweep(input_vars={input_vars_code}, "
            f"result_vars={result_vars_code})\n"
        )

        results_code = (
            "from bokeh.io import output_notebook\n"
            "output_notebook()\n"
            "res.to_auto_plots()\n"
            "res.to_optuna_plots()"
        )

        self.generate_notebook(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            setup_code=setup_code,
            results_code=results_code,
        )

        return super().__call__()


def example_meta_optimization(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaOptimization().to_bench(run_cfg)

    bench.plot_sweep(
        title="Optimization",
        input_vars=[
            bch.p("n_objectives", [1, 2]),
            bch.p("input_dims", [1, 2]),
        ],
    )

    return bench


if __name__ == "__main__":
    example_meta_optimization()
