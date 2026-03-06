"""Meta-generator: Constant Variables.

Shows how to use const_vars to fix parameters at specific values while sweeping others.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "const_vars"

EXAMPLES = ["slice", "compare", "categorical", "noise"]


class MetaConstVars(MetaGeneratorBase):
    """Generate Python examples demonstrating const_vars usage."""

    example = bch.StringSweep(EXAMPLES, doc="Which const_vars example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "slice":
            self._gen_slice()
        elif self.example == "compare":
            self._gen_compare()
        elif self.example == "categorical":
            self._gen_categorical()
        elif self.example == "noise":
            self._gen_noise()

        return super().__call__()

    def _gen_slice(self):
        """Fix one parameter to reduce a 3D sweep to a 2D slice."""
        self.generate_sweep_example(
            title="Const Vars: Slicing a 3D Space",
            output_dir=OUTPUT_DIR,
            filename="const_vars_slice",
            function_name="example_const_vars_slice",
            benchable_class="BenchableObject",
            benchable_module="bencher.example.meta.example_meta",
            input_vars='["float1", "float2"]',
            result_vars='["distance"]',
            const_vars="dict(float3=0.5)",
            run_kwargs={"level": 3},
        )

    def _gen_compare(self):
        """Compare the same sweep at different fixed values of a parameter."""
        imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )
        body = (
            "bench = BenchableObject().to_bench(run_cfg)\n"
            "for float2_val in [0.0, 0.5, 1.0]:\n"
            "    bench.plot_sweep(\n"
            '        title=f"float1 sweep with float2={float2_val}",\n'
            '        input_vars=["float1"],\n'
            '        result_vars=["distance"],\n'
            "        const_vars=dict(float2=float2_val, float3=0.0),\n"
            "    )\n"
        )
        self.generate_example(
            title="Const Vars: Comparing Slices",
            output_dir=OUTPUT_DIR,
            filename="const_vars_compare",
            function_name="example_const_vars_compare",
            imports=imports,
            body=body,
            run_kwargs={"level": 4},
        )

    def _gen_categorical(self):
        """Fix a categorical variable while sweeping others."""
        imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )
        body = (
            "bench = BenchableObject().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Sweep float1 x variant, with wave fixed to False",\n'
            '    input_vars=["float1", "variant"],\n'
            '    result_vars=["distance"],\n'
            "    const_vars=dict(wave=False),\n"
            ")\n"
            "bench.plot_sweep(\n"
            '    title="Sweep float1 x variant, with wave fixed to True",\n'
            '    input_vars=["float1", "variant"],\n'
            '    result_vars=["distance"],\n'
            "    const_vars=dict(wave=True),\n"
            ")\n"
        )
        self.generate_example(
            title="Const Vars: Fixing Categorical Parameters",
            output_dir=OUTPUT_DIR,
            filename="const_vars_categorical",
            function_name="example_const_vars_categorical",
            imports=imports,
            body=body,
            run_kwargs={"level": 4},
        )

    def _gen_noise(self):
        """Set a non-default configuration parameter while benchmarking."""
        self.generate_sweep_example(
            title="Const Vars: Setting Non-Default Configuration",
            output_dir=OUTPUT_DIR,
            filename="const_vars_noise",
            function_name="example_const_vars_noise",
            benchable_class="BenchableObject",
            benchable_module="bencher.example.meta.example_meta",
            input_vars='["float1", "float2"]',
            result_vars='["distance", "sample_noise"]',
            const_vars="dict(noise_scale=0.3)",
            run_kwargs={"level": 3},
        )


def example_meta_const_vars(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaConstVars().to_bench(run_cfg)

    bench.plot_sweep(
        title="Constant Variables",
        input_vars=[bch.p("example", EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_const_vars)
