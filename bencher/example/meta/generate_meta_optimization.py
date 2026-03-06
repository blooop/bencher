"""Meta-generator: Optimization & Pareto.

Generates four progressively complex optimization examples that show how to
use Optuna-backed optimization in Bencher:

1. **1 objective, 1D** — simplest case: maximise a single metric by tuning one parameter.
2. **1 objective, 2D** — same goal over a 2-dimensional design space.
3. **2 objectives, 1D** — introduce competing objectives (performance vs cost) and Pareto fronts.
4. **2 objectives, 2D** — full multi-objective optimisation over a 2D space.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "optimization"

# ── Per-variant metadata ────────────────────────────────────────────────────
# Each key is (n_objectives, input_dims).

_TITLES = {
    (1, 1): "Single-Objective 1D Optimization",
    (1, 2): "Single-Objective 2D Optimization",
    (2, 1): "Multi-Objective 1D Optimization",
    (2, 2): "Multi-Objective 2D Optimization",
}

_MODULE_DOCSTRINGS = {
    (1, 1): (
        "Single-Objective 1D Optimization — Maximize performance by tuning one parameter.\n"
        "\n"
        "The simplest Optuna example: sweep a single design parameter (x) and\n"
        "let Optuna find the value that maximises 'performance'.  Noise is added\n"
        "to simulate real-world measurement variability.\n"
        "\n"
        "Concepts demonstrated:\n"
        "  - Enabling Optuna via ``run_cfg.use_optuna = True``\n"
        "  - Parameter importance and optimization history plots\n"
    ),
    (1, 2): (
        "Single-Objective 2D Optimization — Maximize performance over a 2D design space.\n"
        "\n"
        "Extends the 1D case by adding a second design parameter (y).  Optuna\n"
        "must now navigate a 2-dimensional landscape to find the peak of\n"
        "'performance'.  The contour / slice plots show how each parameter\n"
        "contributes to the objective.\n"
        "\n"
        "Concepts demonstrated:\n"
        "  - Multi-parameter search spaces\n"
        "  - 2D contour and slice visualizations\n"
    ),
    (2, 1): (
        "Multi-Objective 1D Optimization — Balance performance vs. cost.\n"
        "\n"
        "Introduces a second objective: 'cost' (minimize) alongside 'performance'\n"
        "(maximize).  Because the objectives compete — higher x raises both\n"
        "performance and cost — there is no single best solution.  Instead,\n"
        "Optuna finds a set of Pareto-optimal trade-offs.\n"
        "\n"
        "Concepts demonstrated:\n"
        "  - Competing objectives with different optimization directions\n"
        "  - Pareto front visualization\n"
    ),
    (2, 2): (
        "Multi-Objective 2D Optimization — Pareto front over a 2D design space.\n"
        "\n"
        "The most complex variant: two objectives and two design parameters.\n"
        "The Pareto front now captures richer trade-offs because both x and y\n"
        "influence the performance-cost balance in different ways.\n"
        "\n"
        "Concepts demonstrated:\n"
        "  - Full multi-objective optimization\n"
        "  - Pareto front in a higher-dimensional design space\n"
        "  - Parameter importance across multiple objectives\n"
    ),
}

_FUNCTION_DOCSTRINGS = {
    (1, 1): (
        "Maximize performance by sweeping parameter x.\n"
        "\n"
        "    Uses Optuna to find the x value that maximises the\n"
        "    'performance' objective with Gaussian noise (scale=0.1)."
    ),
    (1, 2): (
        "Maximize performance by sweeping parameters x and y.\n"
        "\n"
        "    Uses Optuna to navigate a 2D design space and find the\n"
        "    (x, y) combination that maximises 'performance'."
    ),
    (2, 1): (
        "Balance performance (maximize) vs. cost (minimize) over x.\n"
        "\n"
        "    Demonstrates Pareto optimization: Optuna discovers a set\n"
        "    of trade-off solutions where improving one objective\n"
        "    necessarily worsens the other."
    ),
    (2, 2): (
        "Balance performance vs. cost over a 2D design space.\n"
        "\n"
        "    Full multi-objective optimization with two design\n"
        "    parameters (x, y) and two competing objectives.  The\n"
        "    resulting Pareto front shows optimal trade-offs."
    ),
}


class MetaOptimization(MetaGeneratorBase):
    """Generate Python examples demonstrating optimization features."""

    n_objectives = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of objectives")
    input_dims = bch.IntSweep(default=1, bounds=(1, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        key = (self.n_objectives, self.input_dims)
        filename = f"optim_{self.n_objectives}obj_{self.input_dims}d"
        function_name = f"example_optim_{self.n_objectives}obj_{self.input_dims}d"
        title = _TITLES[key]

        if self.n_objectives == 1:
            result_vars_code = '["performance"]'
        else:
            result_vars_code = '["performance", "cost"]'

        if self.input_dims == 1:
            input_vars_code = '["x"]'
        else:
            input_vars_code = '["x", "y"]'

        # Build inline comments for the generated code
        suffix = ", Pareto front)" if self.n_objectives > 1 else ")"
        post_sweep_comment = (
            "Generate Optuna plots (parameter importance, optimization history" + suffix
        )
        body_comments = {
            "run_cfg": "Enable Optuna-backed optimization instead of pure grid sweep",
            "sweep": "Sweep the design space with Gaussian noise to simulate variability",
            "post_sweep": post_sweep_comment,
        }

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
            module_docstring=_MODULE_DOCSTRINGS[key],
            function_docstring=_FUNCTION_DOCSTRINGS[key],
            body_comments=body_comments,
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
