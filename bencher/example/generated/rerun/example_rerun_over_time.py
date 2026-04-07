"""Auto-generated example: Rerun Over Time — track spatial visualizations across time snapshots."""

import math
from datetime import datetime, timedelta

import rerun as rr
import bencher as bn


class RerunOverTimeSweep(bn.ParametrizedSweep):
    """Sweep that logs 2D geometry to rerun, tracked over time.

    Each call to ``benchmark()`` logs a box whose width varies with *theta*
    plus a time-dependent offset, and captures the recording as a ``.rrd``
    file.  Running the sweep multiple times with different ``time_src``
    values creates an over_time history that can be scrubbed via a slider.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

    out_sin = bn.ResultFloat(units="v", doc="sin of theta")
    out_rerun = bn.ResultRerun(width=400, height=400)

    _time_offset = 0.0

    def benchmark(self):
        self.out_sin = math.sin(self.theta) + self._time_offset
        rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta + self._time_offset, 1]))
        self.out_rerun = bn.capture_rerun_window()


def example_rerun_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Over Time — track spatial visualizations across time snapshots."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = RerunOverTimeSweep()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "over_time",
            input_vars=["theta"],
            result_vars=["out_sin", "out_rerun"],
            description="Rerun window captures tracked over multiple time snapshots. "
            "Each call to plot_sweep with a new time_src appends a snapshot. "
            "The rerun viewer for each sweep point is shown in a slider "
            "that lets you scrub through the time history.",
            post_description="The ``ResultRerun`` type stores ``.rrd`` file paths. "
            "When combined with ``over_time=True``, a Bokeh slider swaps "
            "between the rerun viewer iframes for each time point.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_over_time, level=3, over_time=True)
