"""Auto-generated example: Rerun Capture — embed spatial visualizations in sweep reports."""

import math
import bencher as bn

# Rerun integration requires the optional rerun-sdk package.
# Install with: pip install rerun-sdk
#
# bn.capture_rerun_window() captures the current rerun recording and returns
# a self-contained Panel HTML pane with base64-encoded data inline.
# No local file server is needed — the rerun web viewer is loaded from CDN.
#
# Usage pattern:
#   1. rr.init("my_app")                    -- initialise a recording
#   2. Log data with rr.log(...)            -- shapes, scalars, images, etc.
#   3. self.out = bn.capture_rerun_window() -- capture inline into the report


class RerunSweep(bn.ParametrizedSweep):
    """Demonstrates capturing rerun visualizations during a parameter sweep.

    Each parameter combination logs 2D geometry to rerun and captures the
    viewer state as a ResultContainer panel widget.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

    out_sin = bn.ResultVar(units="v", doc="sin of theta")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)

        # To capture rerun output as a report panel:
        #   import rerun as rr
        #   rr.init("my_app")
        #   rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta, 1]))
        #   self.out_pane = bn.capture_rerun_window(width=300, height=300)
        #
        # capture_rerun_window() embeds the data inline (base64) and loads
        # the rerun viewer from CDN — no local file server needed.


def example_rerun_capture_window(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Capture — embed spatial visualizations in sweep reports."""
    bench = RerunSweep().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["theta"],
        result_vars=["out_sin"],
        description="Rerun is a spatial logging library for 2D/3D visualization. "
        "Bencher integrates with rerun via bn.capture_rerun_window(), which "
        "captures the current recording with base64-encoded data inline and "
        "returns a self-contained Panel HTML pane. No local file server needed. "
        "Install rerun-sdk and uncomment the rr.log() calls in the class to "
        "see live rerun output.",
        post_description="The ResultContainer type stores arbitrary Panel widgets "
        "(HTML, images, embedded viewers). For rerun, each sweep point gets its "
        "own inline snapshot that can be explored interactively in the report.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_capture_window, level=3)
