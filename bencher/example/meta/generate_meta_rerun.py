"""Meta-generator: Rerun visualization integration examples.

Demonstrates how to use the rerun spatial logging library with bencher for
interactive 2D/3D result visualization. The generated examples show the API
patterns but guard the rerun import so they run safely without the optional
rerun-sdk dependency installed.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "rerun"

RERUN_EXAMPLES = [
    "capture_window",
    "rrd_publish",
]


class MetaRerun(MetaGeneratorBase):
    """Generate Python examples demonstrating rerun integration."""

    example = bn.StringSweep(RERUN_EXAMPLES, doc="Which rerun example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "capture_window":
            self._generate_capture_window()
        elif self.example == "rrd_publish":
            self._generate_rrd_publish()

        return super().__call__()

    def _generate_capture_window(self):
        """Capture a rerun viewer window as a Panel widget inside a sweep."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
# Rerun integration requires the optional rerun-sdk package.
# Install with: pip install rerun-sdk
#
# bn.capture_rerun_window() snapshots the current rerun recording into an
# .rrd file and returns a Panel HTML pane embedding the rerun web viewer.
# This lets you log spatial data (2D/3D shapes, time series, images) during
# a parameter sweep and view the results interactively in the report.
#
# Usage pattern:
#   1. rr.init("my_app")                  -- initialise a recording
#   2. Log data with rr.log(...)          -- shapes, scalars, images, etc.
#   3. self.out = bn.capture_rerun_window() -- snapshot into the report
#
# To run the viewer alongside bencher, call bn.run_flask_in_thread() before
# launching the sweep so the .rrd files are served over HTTP.


class RerunSweep(bn.ParametrizedSweep):
    """Demonstrates capturing rerun visualizations during a parameter sweep.

    Each parameter combination logs 2D geometry to rerun and captures the
    viewer state as a ResultContainer panel widget.
    """

    theta = bn.FloatSweep(
        default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5
    )

    out_sin = bn.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)

        # To capture rerun output as a report panel:
        #   import rerun as rr
        #   rr.init("my_app")
        #   rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta, 1]))
        #   self.out_pane = bn.capture_rerun_window(width=300, height=300)
        #
        # capture_rerun_window() saves the current recording to an .rrd file
        # in the cache directory and returns an HTML pane that embeds the
        # rerun web viewer pointed at that file.

        return super().__call__(**kwargs)'''
        body = """\
# In production, start the Flask file server before running sweeps:
# bn.run_flask_in_thread()

bench = RerunSweep().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["out_sin"],
    description="Rerun is a spatial logging library for 2D/3D visualization. "
    "Bencher integrates with rerun via bn.capture_rerun_window(), which "
    "snapshots the current rerun recording into an .rrd file and returns a "
    "Panel widget that embeds the rerun web viewer. This lets you attach "
    "interactive 2D/3D visualizations to each point in a parameter sweep. "
    "Install rerun-sdk and uncomment the rr.log() calls in the class to "
    "see live rerun output.",
    post_description="The ResultContainer type stores arbitrary Panel widgets "
    "(HTML, images, embedded viewers). For rerun, each sweep point gets its "
    "own .rrd snapshot that can be explored interactively in the report.",
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
#   bn.run_flask_in_thread()
#       -> Starts a local HTTP server to serve .rrd files from the cache dir


class WaveSweep(bn.ParametrizedSweep):
    """A simple sweep for demonstrating .rrd publishing patterns."""

    frequency = bn.FloatSweep(
        default=1.0, bounds=[0.5, 4.0], doc="Wave frequency", units="Hz"
    )

    amplitude = bn.ResultVar(units="v", doc="Peak amplitude")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
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
        #   pane.show()

        return super().__call__(**kwargs)'''
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
    "bn.run_flask_in_thread() to serve .rrd files from the cache directory.",
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
