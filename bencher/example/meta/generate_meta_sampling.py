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

        common_imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )

        if self.strategy == "uniform":
            imports = common_imports
            body = (
                "benchable = BenchableObject()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                'bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])\n'
            )
        elif self.strategy == "custom_values":
            imports = common_imports
            body = (
                "benchable = BenchableObject()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                "bench.plot_sweep(\n"
                '    input_vars=[bch.p("float1", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],\n'
                '    result_vars=["distance"],\n'
                ")\n"
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
                ")\n"
            )
        else:  # int_vs_float
            imports = (
                "import bencher as bch\n"
                "from bencher.example.meta.benchable_objects import BenchableIntFloat"
            )
            body = (
                "benchable = BenchableIntFloat()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                'bench.plot_sweep(input_vars=["int_input", "float_input"], '
                'result_vars=["output"])\n'
            )

        level = 4 if self.strategy == "uniform" else 3
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            main_extra=f", level={level}",
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
