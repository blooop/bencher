"""Meta-generator: Sampling Strategies.

Shows uniform bounds, custom sample_values, level-based sampling, and Int vs Float.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "sampling"

STRATEGIES = ["uniform", "custom_values", "levels", "int_vs_float"]


class MetaSampling(MetaGeneratorBase):
    """Generate Python examples demonstrating sampling strategies."""

    strategy = bch.StringSweep(STRATEGIES, doc="Sampling strategy to demonstrate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"sampling_{self.strategy}"
        function_name = f"example_sampling_{self.strategy}"
        title = f"Sampling: {self.strategy.replace('_', ' ').title()}"

        if self.strategy == "uniform":
            self.generate_sweep_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                benchable_class="BenchableObject",
                benchable_module="bencher.example.meta.example_meta",
                input_vars='["float1"]',
                result_vars='["distance"]',
                description=(
                    "Uniform sampling distributes points evenly across the parameter bounds. "
                    "The number of samples is controlled by the level parameter."
                ),
                run_kwargs={"level": 4},
            )
        elif self.strategy == "custom_values":
            imports = (
                "import bencher as bch\n"
                "from bencher.example.meta.example_meta import BenchableObject"
            )
            body = (
                "bench = BenchableObject().to_bench(run_cfg)\n"
                "bench.plot_sweep(\n"
                '    input_vars=[bch.p("float1", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],\n'
                '    result_vars=["distance"],\n'
                '    description="Custom sample values let you pick exact points '
                "to evaluate. Use bch.p() to override a variable's sweep values.\",\n"
                ")\n"
            )
            self.generate_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                imports=imports,
                body=body,
                run_kwargs={"level": 3},
            )
        elif self.strategy == "levels":
            imports = (
                "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchMeta"
            )
            body = (
                "bench = BenchMeta().to_bench(run_cfg)\n"
                "bench.plot_sweep(\n"
                '    title="Level-based sampling resolution",\n'
                "    input_vars=[\n"
                '        bch.p("float_vars", [1, 2]),\n'
                '        bch.p("level", [2, 3, 4, 5]),\n'
                "    ],\n"
                "    const_vars=dict(categorical_vars=0),\n"
                '    description="The level parameter controls how many samples are taken along '
                'each axis. Higher levels give finer resolution but take longer.",\n'
                ")\n"
            )
            self.generate_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                imports=imports,
                body=body,
                run_kwargs={"level": 3},
            )
        else:  # int_vs_float
            self.generate_sweep_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                benchable_class="BenchableIntFloat",
                benchable_module="bencher.example.meta.benchable_objects",
                input_vars='["int_input", "float_input"]',
                result_vars='["output"]',
                description=(
                    "Integer sweeps produce discrete steps while float sweeps produce "
                    "continuous curves. Compare how the plot changes between the two types."
                ),
                run_kwargs={"level": 3},
            )

        return super().__call__()


def example_meta_sampling(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaSampling().to_bench(run_cfg)

    bench.plot_sweep(
        title="Sampling Strategies",
        input_vars=[bch.p("strategy", STRATEGIES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_sampling)
