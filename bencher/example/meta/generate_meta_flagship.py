"""Meta-generator: Flagship inline examples.

Generates a small set of examples that define their domain class inline so
users can see the full pattern without tracing imports.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "flagship"

FLAGSHIP_EXAMPLES = [
    "line_plot",
    "bar_chart",
    "heatmap",
]


class MetaFlagship(MetaGeneratorBase):
    """Generate flagship examples with inline class definitions."""

    example = bch.StringSweep(FLAGSHIP_EXAMPLES, doc="Which flagship example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "line_plot":
            self._generate_line_plot()
        elif self.example == "bar_chart":
            self._generate_bar_chart()
        elif self.example == "heatmap":
            self._generate_heatmap()

        return super().__call__()

    def _generate_line_plot(self):
        """1D float sweep — simplest line plot with inline class."""
        imports = "import math\nimport bencher as bch"
        class_code = '''\
class WaveFunction(bch.ParametrizedSweep):
    """A simple wave function that maps an angle to its sine value.

    This is the simplest possible bencher example: one float input swept
    across its bounds, producing one scalar result plotted as a line.
    """

    theta = bch.FloatSweep(
        default=0, bounds=[0, 2 * math.pi], doc="Input angle", units="rad"
    )

    amplitude = bch.ResultVar(units="V", doc="Sine of the input angle")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.amplitude = math.sin(self.theta)
        return super().__call__()'''
        body = """\
bench = WaveFunction().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["amplitude"],
    description="Sweep a single float variable to produce a 1D line plot. "
    "This is the most basic bencher pattern: define a ParametrizedSweep class, "
    "implement __call__, and pass it to bench.plot_sweep().",
    post_description="The plot shows a clean sine curve. Try adding noise_scale "
    "or repeats to see how bencher handles uncertainty.",
)
"""
        self.generate_example(
            title="Line Plot — Inline Class Definition",
            output_dir=OUTPUT_DIR,
            filename="flagship_line_plot",
            function_name="example_flagship_line_plot",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 4},
        )

    def _generate_bar_chart(self):
        """Categorical sweep — simplest bar chart with inline class."""
        imports = "import bencher as bch"
        class_code = '''\
class ServerBenchmark(bch.ParametrizedSweep):
    """Compares response times across different server configurations.

    This example sweeps a categorical variable (server region) and records
    a scalar metric, producing a bar chart. Define your own categories as
    a StringSweep or EnumSweep.
    """

    region = bch.StringSweep(
        ["us-east", "us-west", "eu-west", "ap-south"],
        doc="Cloud region for the deployment",
    )

    latency = bch.ResultVar(units="ms", doc="Average response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # Simulated latencies per region
        region_latency = {
            "us-east": 45.0,
            "us-west": 62.0,
            "eu-west": 120.0,
            "ap-south": 180.0,
        }
        self.latency = region_latency[self.region]
        return super().__call__()'''
        body = """\
bench = ServerBenchmark().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["region"],
    result_vars=["latency"],
    description="Sweep a categorical variable to produce a bar chart. "
    "Each category is evaluated once and the result plotted as a bar.",
    post_description="US-East has the lowest latency. In a real scenario you would "
    "add repeats to capture variance across measurements.",
)
"""
        self.generate_example(
            title="Bar Chart — Inline Class Definition",
            output_dir=OUTPUT_DIR,
            filename="flagship_bar_chart",
            function_name="example_flagship_bar_chart",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 4},
        )

    def _generate_heatmap(self):
        """2D float sweep — simplest heatmap with inline class."""
        imports = "import math\nimport bencher as bch"
        class_code = '''\
class TerrainSampler(bch.ParametrizedSweep):
    """Samples elevation across a 2D terrain grid.

    Two float inputs are swept to produce a 2D heatmap. The underlying
    function uses sine/cosine to create an interesting terrain pattern.
    """

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="East-west position")
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="North-south position")

    elevation = bch.ResultVar(units="m", doc="Terrain elevation at (x, y)")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.elevation = (
            math.sin(2 * math.pi * self.x) * math.cos(2 * math.pi * self.y)
            + 0.5 * math.sin(4 * math.pi * self.x * self.y)
        )
        return super().__call__()'''
        body = """\
bench = TerrainSampler().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["x", "y"],
    result_vars=["elevation"],
    description="Sweep two float variables to produce a 2D heatmap. "
    "The Cartesian product of x and y values is evaluated, and elevation "
    "is color-coded on a grid.",
    post_description="Notice the interference pattern created by the sine/cosine "
    "interaction. Increase the level parameter for finer resolution.",
)
"""
        self.generate_example(
            title="Heatmap — Inline Class Definition",
            output_dir=OUTPUT_DIR,
            filename="flagship_heatmap",
            function_name="example_flagship_heatmap",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )


def example_meta_flagship(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaFlagship().to_bench(run_cfg)

    bench.plot_sweep(
        title="Flagship Inline Examples",
        input_vars=[bch.p("example", FLAGSHIP_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_flagship)
