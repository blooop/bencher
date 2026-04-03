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
        elif self.example == "rrd_publish":
            self._generate_rrd_publish()

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
        self.out_rerun = bn.capture_rerun_window(width=400, height=400)'''
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

    def _generate_rrd_publish(self):
        """Publish .rrd recordings to a git branch for sharing."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
# Rerun recordings can be published to a git branch and viewed via the
# hosted rerun web viewer at https://app.rerun.io/.
#
# Workflow:
#   1. rr.init("my_app", spawn=True)  -- start rerun with a local .rrd file
#   2. rr.save("data.rrd")            -- persist the recording
#   3. Log data with rr.log(...)
#   4. bn.publish_and_view_rrd(...)    -- push .rrd to a git branch and
#      return a Panel pane that loads it in the hosted viewer
#
# Alternatively, use bn.rrd_to_pane(url) to view any .rrd file served
# over HTTP (local or remote) in a Panel HTML pane.
#
# Functions:
#   bn.rrd_to_pane(url, width, height)
#       -> Panel HTML pane embedding the rerun web viewer for the given URL
#
#   bn.publish_and_view_rrd(file_path, remote, branch_name, content_callback)
#       -> Pushes the .rrd file to a git branch and returns rrd_to_pane()
#
#   bn.run_file_server()
#       -> Starts a local file server to serve .rrd files from the cache dir


class WaveSweep(bn.ParametrizedSweep):
    """A simple sweep for demonstrating .rrd publishing patterns."""

    frequency = bn.FloatSweep(
        default=1.0, bounds=[0.5, 4.0], doc="Wave frequency", units="Hz"
    )

    amplitude = bn.ResultFloat(units="v", doc="Peak amplitude")

    def benchmark(self):
        self.amplitude = math.sin(self.frequency * math.pi)

        # To publish rerun data:
        #   import rerun as rr
        #   rr.init("my_app", spawn=True)
        #   rr.save("data.rrd")
        #   rr.log("wave", rr.Scalars(self.amplitude))
        #
        # Then view locally:
        #   pane = bn.rrd_to_pane("http://127.0.0.1:8001/data.rrd")
        #   pane.show()
        #
        # Or publish to a git branch:
        #   pane = bn.publish_and_view_rrd(
        #       "data.rrd",
        #       remote="https://github.com/user/repo.git",
        #       branch_name="rerun_data",
        #       content_callback=bn.github_content,
        #   )
        #   pane.show()'''
        body = """\
bench = WaveSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["frequency"],
    result_vars=["amplitude"],
    description="Rerun .rrd recordings can be shared by publishing them to a "
    "git branch or serving them over HTTP. Use bn.rrd_to_pane(url) to embed "
    "the hosted rerun web viewer in a Panel pane, or "
    "bn.publish_and_view_rrd() to push the .rrd file to a git branch and "
    "view it immediately. Start a local file server with "
    "bn.run_file_server() to serve .rrd files from the cache directory.\\n"
    "The file server uses Python's stdlib http.server — no extra dependencies.",
    post_description="This example shows the sweep pattern. To see live rerun "
    "output, install rerun-sdk (pip install rerun-sdk) and uncomment the "
    "rr.log() calls in the class definition.",
)
"""
        self.generate_example(
            title="Rerun Publishing — share .rrd recordings via git or HTTP",
            output_dir=OUTPUT_DIR,
            filename="rerun_rrd_publish",
            function_name="example_rerun_rrd_publish",
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
