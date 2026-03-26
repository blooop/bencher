"""Meta-generator: Optimization & Pareto.

Shows optimization direction, Optuna integration, multi-objective Pareto,
over-time importance analysis, and optimize=False aggregation.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "optimization"

CLASS_CODE = "\n".join(
    [
        "class ServerOptimizer(bn.ParametrizedSweep):",
        '    """Optimizes server configuration for performance vs cost tradeoff."""',
        "",
        '    cpu_cores = bn.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")',
        '    memory_gb = bn.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")',
        "",
        '    performance = bn.ResultVar("score", bn.OptDir.maximize, doc="Performance score (maximize)")',
        '    cost = bn.ResultVar("$/hr", bn.OptDir.minimize, doc="Hourly cost (minimize)")',
        "",
        '    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")',
        "",
        "    def __call__(self, **kwargs):",
        "        self.update_params_from_kwargs(**kwargs)",
        "        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10",
        "        self.cost = 0.05 * self.cpu_cores + 0.02 * self.memory_gb",
        "        if self.noise_scale > 0:",
        "            self.performance += random.gauss(0, self.noise_scale * 5)",
        "            self.cost += random.gauss(0, self.noise_scale * 0.1)",
        "        return super().__call__()",
    ]
)

# Class with a _drift field for over_time examples (performance degrades over time)
CLASS_CODE_OVERTIME = "\n".join(
    [
        "class ServerOptimizer(bn.ParametrizedSweep):",
        '    """Optimizes server config — performance drifts over time."""',
        "",
        '    cpu_cores = bn.FloatSweep(default=4, bounds=[1, 32], doc="Number of CPU cores")',
        '    memory_gb = bn.FloatSweep(default=8, bounds=[1, 64], doc="Memory in GB")',
        "",
        '    performance = bn.ResultVar("score", bn.OptDir.maximize, doc="Performance score")',
        "",
        '    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")',
        "",
        "    _drift = 0.0",
        "",
        "    def __call__(self, **kwargs):",
        "        self.update_params_from_kwargs(**kwargs)",
        "        self.performance = math.log2(self.cpu_cores + 1) * math.sqrt(self.memory_gb) * 10",
        "        self.performance *= (1.0 - self._drift * 0.15)  # degrade over time",
        "        if self.noise_scale > 0:",
        "            self.performance += random.gauss(0, self.noise_scale * 5)",
        "        return super().__call__()",
    ]
)

# Class with optimize=False on a categorical var for aggregation examples
CLASS_CODE_AGG = "\n".join(
    [
        "class AlgorithmBench(bn.ParametrizedSweep):",
        '    """Finds best learning rate across algorithms (aggregated)."""',
        "",
        "    algorithm = bn.StringSweep(",
        '        ["gradient_descent", "adam", "rmsprop"],',
        '        doc="Optimization algorithm",',
        "        optimize=False,  # sweep but don't optimize — aggregate results",
        "    )",
        '    learning_rate = bn.FloatSweep(default=0.01, bounds=[0.001, 1.0], doc="Learning rate")',
        "",
        '    loss = bn.ResultVar("loss", bn.OptDir.minimize, doc="Training loss (minimize)")',
        "",
        "    def __call__(self, **kwargs):",
        "        self.update_params_from_kwargs(**kwargs)",
        '        algo_sensitivity = {"gradient_descent": 1.0, "adam": 0.6, "rmsprop": 0.8}',
        "        optimal_lr = 0.01 * algo_sensitivity[self.algorithm]",
        "        self.loss = (math.log10(self.learning_rate) - math.log10(optimal_lr)) ** 2",
        "        self.loss += random.gauss(0, 0.02)",
        "        return super().__call__()",
    ]
)


class MetaOptimization(MetaGeneratorBase):
    """Generate Python examples demonstrating optimization features."""

    n_objectives = bn.IntSweep(default=1, bounds=(1, 2), doc="Number of objectives")
    input_dims = bn.IntSweep(default=1, bounds=(1, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        obj_word = "1_objective" if self.n_objectives == 1 else "2_objectives"
        filename = f"optim_{obj_word}_{self.input_dims}d"
        function_name = f"example_optim_{obj_word}_{self.input_dims}d"
        title = f"Optimise {self.n_objectives} objective(s), {self.input_dims}D input"

        if self.n_objectives == 1:
            result_vars_code = '["performance"]'
        else:
            result_vars_code = '["performance", "cost"]'

        if self.input_dims == 1:
            input_vars_code = '["cpu_cores"]'
        else:
            input_vars_code = '["cpu_cores", "memory_gb"]'

        if self.n_objectives == 1:
            description = (
                f"Single-objective optimization over {self.input_dims}D input space using Optuna. "
                "The optimizer searches for the parameter combination that maximizes performance."
            )
            post_description = (
                "The Optuna importance plot shows which input parameters most affect the objective."
            )
        else:
            description = (
                f"Multi-objective optimization over {self.input_dims}D input space using Optuna. "
                "The optimizer finds the Pareto front trading off performance vs cost."
            )
            post_description = (
                "The Pareto front shows optimal trade-offs — no point can improve one "
                "objective without worsening the other."
            )

        level = 2 if self.input_dims >= 2 else 3
        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class="ServerOptimizer",
            benchable_module=None,
            class_code=CLASS_CODE,
            extra_imports=["import math", "import random"],
            input_vars=input_vars_code,
            result_vars=result_vars_code,
            const_vars="dict(noise_scale=0.1)",
            description=description,
            post_description=post_description,
            run_kwargs={"level": level, "repeats": 3, "optimise": 30},
        )

        return super().__call__()


class MetaOptimizationOverTime(MetaGeneratorBase):
    """Generate optimization examples that run over time with importance analysis.

    The importance plots show repeat AND over_time alongside input parameters,
    revealing whether measurement noise or temporal drift affects results.
    """

    input_dims = bn.IntSweep(default=1, bounds=(1, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"optim_over_time_{self.input_dims}d"
        function_name = f"example_optim_over_time_{self.input_dims}d"
        title = f"Optimise Over Time: {self.input_dims}D input"

        if self.input_dims == 1:
            input_vars_code = '["cpu_cores"]'
        else:
            input_vars_code = '["cpu_cores", "memory_gb"]'

        description = (
            f"Optimization over {self.input_dims}D input space with temporal drift. "
            "Performance degrades over successive runs. The importance analysis shows "
            "repeat, over_time, and input parameters — revealing whether noise or "
            "temporal drift dominates."
        )
        post_description = (
            "Check the 'Parameter Importance With Repeats' plot: if over_time has high "
            "importance, results are drifting. If repeat is high, measurements are noisy."
        )

        body_lines = [
            "run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)",
            "benchable = ServerOptimizer()",
            "bench = benchable.to_bench(run_cfg)",
            "_base_time = datetime(2000, 1, 1)",
            "for i in range(4):",
            "    benchable._drift = float(i)",
            "    run_cfg.clear_cache = True",
            "    run_cfg.clear_history = i == 0",
            "    bench.plot_sweep(",
            '        "over_time",',
            f"        input_vars={input_vars_code},",
            '        result_vars=["performance"],',
            "        const_vars=dict(noise_scale=0.15),",
            f"        description={description!r},",
            f"        post_description={post_description!r},",
            "        run_cfg=run_cfg,",
            "        time_src=_base_time + timedelta(seconds=i),",
            "    )",
        ]

        self.generate_example(
            title=title,
            output_dir="optimization_over_time",
            filename=filename,
            function_name=function_name,
            imports=(
                "import math\nimport random\nfrom datetime import datetime, timedelta"
                "\n\nimport bencher as bn"
            ),
            body="\n".join(body_lines) + "\n",
            class_code=CLASS_CODE_OVERTIME,
            run_kwargs={"level": 2, "optimise": 30, "over_time": True},
        )

        return super().__call__()


class MetaOptimizationAggregated(MetaGeneratorBase):
    """Generate examples showing optimize=False aggregation with Optuna.

    A categorical variable (algorithm) is swept but not optimized — Optuna
    finds the best learning_rate by averaging loss across all algorithms.
    """

    with_over_time = bn.BoolSweep(default=False, doc="Include over_time dimension")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.with_over_time:
            filename = "optim_aggregated_over_time"
            function_name = "example_optim_aggregated_over_time"
            title = "Aggregated Optimisation (Over Time)"
            description = (
                "Finds the best learning rate averaged across algorithms, tracked over time. "
                "algorithm has optimize=False so Optuna aggregates over it. "
                "The importance plot shows learning_rate, repeat, and over_time."
            )
            post_description = (
                "The importance plot reveals which factors matter: the optimized parameter "
                "(learning_rate), measurement noise (repeat), or temporal drift (over_time)."
            )

            body_lines = [
                "run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)",
                "benchable = AlgorithmBench()",
                "bench = benchable.to_bench(run_cfg)",
                "_base_time = datetime(2000, 1, 1)",
                "for i in range(3):",
                "    run_cfg.clear_cache = True",
                "    run_cfg.clear_history = i == 0",
                "    bench.plot_sweep(",
                '        "over_time",',
                '        input_vars=["algorithm", "learning_rate"],',
                '        result_vars=["loss"],',
                f"        description={description!r},",
                f"        post_description={post_description!r},",
                "        run_cfg=run_cfg,",
                "        time_src=_base_time + timedelta(seconds=i),",
                "    )",
            ]

            self.generate_example(
                title=title,
                output_dir="optimization_aggregated",
                filename=filename,
                function_name=function_name,
                imports=(
                    "import math\nimport random\nfrom datetime import datetime, timedelta"
                    "\n\nimport bencher as bn"
                ),
                body="\n".join(body_lines) + "\n",
                class_code=CLASS_CODE_AGG,
                run_kwargs={"level": 3, "optimise": 30, "over_time": True},
            )
        else:
            filename = "optim_aggregated"
            function_name = "example_optim_aggregated"
            title = "Aggregated Optimisation"
            description = (
                "Finds the best learning rate averaged across algorithms. "
                "algorithm has optimize=False so Optuna only suggests learning_rate "
                "and averages loss over all algorithm choices."
            )
            post_description = (
                "The importance plot shows learning_rate and repeat — algorithm is "
                "aggregated away. Compare 'With Repeats' vs 'Without Repeats' to see "
                "if measurement noise affects the result."
            )

            self.generate_sweep_example(
                title=title,
                output_dir="optimization_aggregated",
                filename=filename,
                function_name=function_name,
                benchable_class="AlgorithmBench",
                benchable_module=None,
                class_code=CLASS_CODE_AGG,
                extra_imports=["import math", "import random"],
                input_vars='["algorithm", "learning_rate"]',
                result_vars='["loss"]',
                description=description,
                post_description=post_description,
                run_kwargs={"level": 3, "repeats": 3, "optimise": 30},
            )

        return super().__call__()


def example_meta_optimization(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaOptimization().to_bench(run_cfg)

    bench.plot_sweep(
        title="Optimization",
        input_vars=[
            bn.sweep("n_objectives", [1, 2]),
            bn.sweep("input_dims", [1, 2]),
        ],
    )

    return bench


def example_meta_optimization_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaOptimizationOverTime().to_bench(run_cfg)

    bench.plot_sweep(
        title="Optimization Over Time",
        input_vars=[bn.sweep("input_dims", [1, 2])],
    )

    return bench


def example_meta_optimization_aggregated(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaOptimizationAggregated().to_bench(run_cfg)

    bench.plot_sweep(
        title="Optimization Aggregated",
        input_vars=[bn.sweep("with_over_time", [False])],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_optimization)
