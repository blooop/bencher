"""Meta-generator: Rerun visualization integration examples.

Demonstrates how to use the rerun spatial logging library with bencher for
interactive 2D/3D result visualization. The generated examples show the API
patterns but guard the rerun import so they run safely without the optional
rerun-sdk dependency installed.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "rerun"

RERUN_EXAMPLES = [
    "capture_window",
]


class MetaRerun(MetaGeneratorBase):
    """Generate Python examples demonstrating rerun integration."""

    example = bn.StringSweep(RERUN_EXAMPLES, doc="Which rerun example to generate")

    def benchmark(self):
        if self.example == "capture_window":
            self._generate_capture_window()

    def _generate_capture_window(self):
        """Capture a rerun viewer window as a Panel widget inside a sweep."""
        imports = "import math\nimport rerun as rr\nimport bencher as bn"
        class_code = '''
class RerunSweep(bn.ParametrizedSweep):
    """Sweep that logs 2D geometry to rerun for each parameter combination.

    Each call to ``benchmark()`` logs a box whose width varies with *theta*
    and captures the recording as a ``.rrd`` file.  The CDN-hosted rerun
    web viewer renders each snapshot inline in the report.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

    out_sin = bn.ResultFloat(units="v", doc="sin of theta")
    out_rerun = bn.ResultRerun(width=400, height=400)

    def benchmark(self):
        self.out_sin = math.sin(self.theta)
        rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta, 1]))
        self.out_rerun = bn.capture_rerun_window()'''
        body = """\
bench = RerunSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["out_sin", "out_rerun"],
    description="Rerun is a spatial logging library for 2D/3D visualization. "
    "Bencher integrates with rerun via ``bn.capture_rerun_window()``, which "
    "drains the current recording to a ``.rrd`` file and embeds a CDN-hosted "
    "viewer in the report.  Each sweep point gets its own interactive viewer.",
    post_description="The ``ResultRerun`` type stores ``.rrd`` file paths and "
    "renders them with the ``@rerun-io/web-viewer`` loaded from CDN.  "
    "No local viewer server or extra ports are needed.",
)
"""
        self.generate_example(
            title="Rerun Capture — embed spatial visualizations in sweep reports",
            output_dir=OUTPUT_DIR,
            filename="rerun_capture_window",
            function_name="example_rerun_capture_window",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )


def example_meta_rerun(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaRerun().to_bench(run_cfg)

    bench.plot_sweep(
        title="Rerun Integration",
        input_vars=[bn.sweep("example", RERUN_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_rerun)
