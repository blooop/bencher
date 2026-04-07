"""Auto-generated example: Rerun Over Time — track spatial visualizations across time snapshots."""

from datetime import datetime, timedelta

import bencher as bn
from bencher.example.example_rerun_over_time import SweepRerunOverTime


def example_rerun_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Over Time — track spatial visualizations across time snapshots."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = SweepRerunOverTime()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable.time_offset = offset
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
