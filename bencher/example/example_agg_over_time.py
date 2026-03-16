"""Demo: aggregate over a swept dimension to produce a curve over time with error bounds.

When ``over_time=True`` and a float input is swept, aggregating over that input
(via ``agg_over_dims``) collapses it to mean +/- std at each time point.  The
resulting ``CurveResult`` shows how the aggregate metric evolves over time with
error bounds derived from the spread across the swept values.

Run:
    python bencher/example/example_agg_over_time.py
"""

from datetime import datetime, timedelta

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_agg_over_time(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)

    time_offsets = [0.0, 0.5, 1.0, 1.5, 2.0]
    base_time = datetime(2000, 1, 1)
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset  # pylint: disable=protected-access
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = False
        bench.plot_sweep(
            "agg_over_time",
            input_vars=["float1"],
            result_vars=["distance"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )

    res = bench.results[-1]
    bench.report.append(res.to(bch.CurveResult, agg_over_dims=["float1"]))
    return bench


if __name__ == "__main__":
    bch.run(example_agg_over_time, save=True)
