"""Example: Rerun window captures with over_time tracking.

Demonstrates per-variable ``max_time_events``: the ``out_rerun`` result
keeps only the 2 most recent time snapshots (because .rrd files are large),
while ``out_sin`` retains the full history.
"""

import math
import rerun as rr
import bencher as bn
from datetime import datetime, timedelta


class SweepRerunOverTime(bn.ParametrizedSweep):
    """Sweep that logs 2D geometry to rerun, tracked over time.

    Set ``time_offset`` before each :meth:`plot_sweep` call to vary the
    benchmark output across time snapshots.  It is a plain float (not a
    sweep parameter) so it is not included in the Cartesian product — the
    over_time axis is controlled externally via ``time_src``.

    ``out_rerun`` uses ``max_time_events=2`` so only the 2 most recent
    .rrd snapshots are kept, while ``out_sin`` retains the full history.
    """

    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Box half-size", units="rad", samples=5)

    out_sin = bn.ResultFloat(units="v", doc="sin of theta")
    out_rerun = bn.ResultRerun(width=400, height=400, max_time_events=2)

    time_offset = 0.0

    def benchmark(self):
        self.out_sin = math.sin(self.theta) + self.time_offset
        rr.log("boxes", rr.Boxes2D(half_sizes=[self.theta + self.time_offset, 1]))
        self.out_rerun = bn.capture_rerun_window()


def example_rerun_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun window captures tracked over multiple time snapshots."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()

    benchable = SweepRerunOverTime()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)

    for i, offset in enumerate([0.0, 0.5, 1.0, 1.5, 2.0]):
        benchable.time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "over_time",
            input_vars=["theta"],
            result_vars=["out_sin", "out_rerun"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_over_time, level=3, over_time=True)
