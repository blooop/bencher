"""Auto-generated example: Rerun Capture — embed spatial visualizations in sweep reports."""

from typing import Any

import math
import bencher as bn

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
# To run the viewer alongside bencher, call bn.run_file_server() before
# launching the sweep so the .rrd files are served over HTTP (uses stdlib
# http.server, no extra dependencies required).


class RerunSweep(bn.ParametrizedSweep):
    """Demonstrates capturing rerun visualizations during a parameter sweep.

    Each parameter combination logs 2D geometry to rerun and captures the
    viewer state as a ResultContainer panel widget.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

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

        return super().__call__(**kwargs)


def example_rerun_capture_window(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Capture — embed spatial visualizations in sweep reports."""
    # In production, start the file server before running sweeps:
    # bn.run_file_server()

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

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_capture_window, level=3)
