"""Auto-generated example: Rerun Capture — embed spatial visualizations in sweep reports."""

import math
import rerun as rr
import bencher as bn


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
        self.out_rerun = bn.capture_rerun_window()


def example_rerun_capture_window(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Capture — embed spatial visualizations in sweep reports."""
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

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_capture_window, level=3)
