"""Meta-generator: Sampling Strategies.

Shows uniform bounds, custom sample_values, and Int vs Float.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "sampling"

STRATEGIES = ["uniform", "custom_values", "int_vs_float"]

# -- Inline class definitions for self-contained examples -----------------------

_UNIFORM_CLASS_CODE = '''\
class UniformSampler(bn.ParametrizedSweep):
    """Demonstrates uniform sampling across a parameter range."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultFloat(units="ms", doc="Response latency")

    def benchmark(self):
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)'''

_CUSTOM_CLASS_CODE = '''\
class CustomSampler(bn.ParametrizedSweep):
    """Demonstrates custom sample value selection."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultFloat(units="ms", doc="Response latency")

    def benchmark(self):
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)'''

_INT_FLOAT_CLASS_CODE = '''\
class IntFloatCompare(bn.ParametrizedSweep):
    """Compares integer vs float sweep behaviour."""

    int_input = bn.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bn.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bn.ResultFloat("ul", doc="Computed output")

    def benchmark(self):
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)'''


class MetaSampling(MetaGeneratorBase):
    """Generate Python examples demonstrating sampling strategies."""

    strategy = bn.StringSweep(STRATEGIES, doc="Sampling strategy to demonstrate")

    def benchmark(self):
        function_name = f"example_sampling_{self.strategy}"
        filename = function_name
        title = f"Sampling: {self.strategy.replace('_', ' ').title()}"

        if self.strategy == "uniform":
            self.generate_sweep_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                benchable_class="UniformSampler",
                benchable_module=None,
                input_vars='["load"]',
                result_vars='["latency"]',
                class_code=_UNIFORM_CLASS_CODE,
                extra_imports=["import math"],
                description=(
                    "Uniform sampling distributes points evenly across the parameter bounds. "
                    "The number of samples is controlled by the level parameter."
                ),
                run_kwargs={"level": 4},
            )
        elif self.strategy == "custom_values":
            imports = "import math\nimport bencher as bn"
            body = (
                "bench = CustomSampler().to_bench(run_cfg)\n"
                "\n"
                "# There are several equivalent ways to specify custom sample values:\n"
                "#   1. bn.sweep('load', [0.0, 0.3, 0.7, 1.0])  -- shorthand helper\n"
                "#   2. CustomSampler.param.load.with_sample_values([0.0, 0.3, 0.7, 1.0])\n"
                "#   3. bn.sweep('load', samples=5)  -- override the number of uniform samples\n"
                "\n"
                "# Explicit sample values\n"
                "bench.plot_sweep(\n"
                '    title="Custom Sample Values with bn.sweep()",\n'
                '    input_vars=[bn.sweep("load", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],\n'
                '    result_vars=["latency"],\n'
                '    description="Custom sample values let you pick exact points '
                "to evaluate instead of a uniform sweep. Use bn.sweep('name', [values]) "
                "as shorthand, or Cls.param.name.with_sample_values([values]) for "
                "the explicit form. You can also use bn.sweep('name', samples=N) to "
                'override the number of uniform samples without listing values.",\n'
                '    post_description="The plot shows the function evaluated only at '
                "the six hand-picked load values. Compare with the uniform sampling "
                'example to see the difference in coverage.",\n'
                ")\n"
                "\n"
                "# Override number of uniform samples\n"
                "bench.plot_sweep(\n"
                '    title="Override Uniform Sample Count with bn.sweep()",\n'
                '    input_vars=[bn.sweep("load", samples=5)],\n'
                '    result_vars=["latency"],\n'
                "    description=\"bn.sweep('load', samples=5) overrides how many "
                "uniformly-spaced samples are taken from the variable's bounds, "
                'without listing explicit values.",\n'
                ")\n"
            )
            self.generate_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                imports=imports,
                body=body,
                class_code=_CUSTOM_CLASS_CODE,
                run_kwargs={"level": 3},
            )
        else:  # int_vs_float
            self.generate_sweep_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                benchable_class="IntFloatCompare",
                benchable_module=None,
                input_vars='["int_input", "float_input"]',
                result_vars='["output"]',
                class_code=_INT_FLOAT_CLASS_CODE,
                extra_imports=["import math"],
                description=(
                    "Integer sweeps produce discrete steps while float sweeps produce "
                    "continuous curves. Compare how the plot changes between the two types."
                ),
                run_kwargs={"level": 3},
            )


def example_meta_sampling(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaSampling().to_bench(run_cfg)

    bench.plot_sweep(
        title="Sampling Strategies",
        input_vars=[bn.sweep("strategy", STRATEGIES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_sampling)
