"""Meta-generator: Sampling Strategies.

Shows uniform bounds, custom sample_values, level-based sampling, and Int vs Float.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "sampling"

STRATEGIES = ["uniform", "custom_values", "levels", "int_vs_float"]

# -- Inline class definitions for self-contained examples -----------------------

_UNIFORM_CLASS_CODE = '''\
class UniformSampler(bn.ParametrizedSweep):
    """Demonstrates uniform sampling across a parameter range."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)
        return super().__call__()'''

_CUSTOM_CLASS_CODE = '''\
class CustomSampler(bn.ParametrizedSweep):
    """Demonstrates custom sample value selection."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Server load")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10 + 90 * self.load + 5 * math.sin(math.pi * self.load * 3)
        return super().__call__()'''

_LEVELS_CLASS_CODE = '''\
class LevelDemo(bn.ParametrizedSweep):
    """Demonstrates how sampling level affects resolution."""

    resolution = bn.IntSweep(default=2, bounds=(2, 5), doc="Sampling resolution level")
    points = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Sample point")

    value = bn.ResultVar(units="ul")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.value = math.sin(self.points * math.pi * self.resolution) + self.resolution * 0.1
        return super().__call__()'''

_INT_FLOAT_CLASS_CODE = '''\
class IntFloatCompare(bn.ParametrizedSweep):
    """Compares integer vs float sweep behaviour."""

    int_input = bn.IntSweep(default=5, bounds=[0, 10], doc="Discrete integer input")
    float_input = bn.FloatSweep(default=5.0, bounds=[0.0, 10.0], doc="Continuous float input")

    output = bn.ResultVar("ul", doc="Computed output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.output = math.sin(self.int_input * 0.3) + math.cos(self.float_input * 0.2)
        return super().__call__()'''


class MetaSampling(MetaGeneratorBase):
    """Generate Python examples demonstrating sampling strategies."""

    strategy = bn.StringSweep(STRATEGIES, doc="Sampling strategy to demonstrate")

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
                "#   1. bn.p('load', [0.0, 0.3, 0.7, 1.0])  -- shorthand helper\n"
                "#   2. CustomSampler.param.load.with_sample_values([0.0, 0.3, 0.7, 1.0])\n"
                "#   3. bn.p('load', samples=5)  -- override the number of uniform samples\n"
                "\n"
                "# Explicit sample values\n"
                "bench.plot_sweep(\n"
                '    title="Custom Sample Values with bn.p()",\n'
                '    input_vars=[bn.p("load", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],\n'
                '    result_vars=["latency"],\n'
                '    description="Custom sample values let you pick exact points '
                "to evaluate instead of a uniform sweep. Use bn.p('name', [values]) "
                "as shorthand, or Cls.param.name.with_sample_values([values]) for "
                "the explicit form. You can also use bn.p('name', samples=N) to "
                'override the number of uniform samples without listing values.",\n'
                '    post_description="The plot shows the function evaluated only at '
                "the six hand-picked load values. Compare with the uniform sampling "
                'example to see the difference in coverage.",\n'
                ")\n"
                "\n"
                "# Override number of uniform samples\n"
                "bench.plot_sweep(\n"
                '    title="Override Uniform Sample Count with bn.p()",\n'
                '    input_vars=[bn.p("load", samples=5)],\n'
                '    result_vars=["latency"],\n'
                "    description=\"bn.p('load', samples=5) overrides how many "
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
        elif self.strategy == "levels":
            imports = "import math\nimport bencher as bn"
            levels_desc = (
                "Sample levels let you perform parameter sweeps without "
                "having to decide how many samples to take when defining the class. "
                "If you perform a sweep at level 2, all those points are reused when "
                "sampling at level 3. Higher levels reuse the points from lower "
                "levels to avoid recomputing potentially expensive samples. This "
                "enables a workflow where you quickly see results at low resolution "
                "to sense-check the code, then run at a high level for full "
                "fidelity. When calling a sweep at a high level you can publish "
                "intermediate lower-level results as computation continues, letting "
                "you track progress and end the sweep early when you have "
                "sufficient resolution."
            )
            levels_post = (
                "Each column shows the same function sampled at "
                "a different resolution level. Notice how lower-level sample "
                "points are a subset of higher-level points -- no work is wasted."
            )
            body = (
                "bench = LevelDemo().to_bench(run_cfg)\n"
                "bench.plot_sweep(\n"
                '    title="Level-based sampling resolution",\n'
                "    input_vars=[\n"
                '        "points",\n'
                '        bn.p("resolution", [2, 3, 4, 5]),\n'
                "    ],\n"
                '    result_vars=["value"],\n'
                f"    description={levels_desc!r},\n"
                f"    post_description={levels_post!r},\n"
                ")\n"
            )
            self.generate_example(
                title=title,
                output_dir=OUTPUT_DIR,
                filename=filename,
                function_name=function_name,
                imports=imports,
                body=body,
                class_code=_LEVELS_CLASS_CODE,
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

        return super().__call__()


def example_meta_sampling(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaSampling().to_bench(run_cfg)

    bench.plot_sweep(
        title="Sampling Strategies",
        input_vars=[bn.p("strategy", STRATEGIES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_sampling)
