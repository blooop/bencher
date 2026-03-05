"""Meta-generator: Optimization & Pareto.

Shows optimization direction, Optuna integration, and multi-objective Pareto.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "optimization"


class MetaOptimization(MetaGeneratorBase):
    """Generate Python examples demonstrating optimization features."""

    n_objectives = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of objectives")
    input_dims = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"optim_{self.n_objectives}obj_{self.input_dims}d"
        function_name = f"example_optim_{self.n_objectives}obj_{self.input_dims}d"
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
        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class="BenchableMultiObjective",
            benchable_module="bencher.example.meta.benchable_objects",
            input_vars=input_vars_code,
            result_vars=result_vars_code,
            const_vars="dict(noise_scale=0.1)",
            post_sweep_line="res.to_optuna_plots()",
            run_cfg_lines=["run_cfg.use_optuna = True"],
            run_kwargs={"level": level, "repeats": 3},
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
    bch.run(example_meta_optimization)
