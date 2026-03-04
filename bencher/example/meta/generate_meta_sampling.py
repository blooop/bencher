"""Meta-generator: Sampling Strategies.

Shows uniform bounds, custom sample_values, level-based sampling, and Int vs Float.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "sampling"

STRATEGIES = ["uniform", "custom_values", "levels", "int_vs_float"]


class MetaSampling(MetaGeneratorBase):
    """Generate notebooks demonstrating sampling strategies."""

    strategy = bch.StringSweep(STRATEGIES, doc="Sampling strategy to demonstrate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"sampling_{self.strategy}"
        title = f"Sampling: {self.strategy.replace('_', ' ').title()}"

        if self.strategy == "uniform":
            setup_code = (
                "import bencher as bch\n"
                "from bencher.example.meta.example_meta import BenchableObject\n"
                "run_cfg = bch.BenchRunCfg()\n"
                "run_cfg.level = 4\n"
                "benchable = BenchableObject()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                'res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])\n'
            )
        elif self.strategy == "custom_values":
            setup_code = (
                "import bencher as bch\n"
                "from bencher.example.meta.example_meta import BenchableObject\n"
                "run_cfg = bch.BenchRunCfg()\n"
                "benchable = BenchableObject()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                "res = bench.plot_sweep(\n"
                '    input_vars=[bch.p("float1", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],\n'
                '    result_vars=["distance"],\n'
                ")\n"
            )
        elif self.strategy == "levels":
            setup_code = (
                "import bencher as bch\n"
                "from bencher.example.meta.example_meta import BenchMeta\n"
                "bench = BenchMeta().to_bench()\n"
                "bench.plot_sweep(\n"
                '    title="Level-based sampling resolution",\n'
                "    input_vars=[\n"
                '        bch.p("float_vars", [1, 2]),\n'
                '        bch.p("level", [2, 3, 4, 5]),\n'
                "    ],\n"
                "    const_vars=dict(categorical_vars=0),\n"
                ")\n"
                "res = bench.get_result()\n"
            )
        else:  # int_vs_float
            setup_code = (
                "import bencher as bch\n"
                "from bencher.example.meta.benchable_objects import BenchableIntFloat\n"
                "run_cfg = bch.BenchRunCfg()\n"
                "run_cfg.level = 3\n"
                "benchable = BenchableIntFloat()\n"
                "bench = benchable.to_bench(run_cfg)\n"
                'res = bench.plot_sweep(input_vars=["int_input", "float_input"], '
                'result_vars=["output"])\n'
            )

        self.generate_notebook(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            setup_code=setup_code,
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
    example_meta_sampling()
