"""Demo: aggregate a 2D sweep to visualise distribution evolution over time.

A 2D parameter sweep (float1 x float2) is run at each time snapshot.  Early on
the spatial variation is uniform (tight distribution).  Over time a hot spot
develops at one corner, making the distribution increasingly skewed — the mean
barely moves but the spread and tail grow dramatically.

Three views are shown:
1. Raw 2D heatmap with an over_time slider — explore each snapshot.
2. CurveResult (mean +/- std) — the classic scalar summary over time.
3. BandResult (percentile bands) — reveals the growing skew that mean +/- std hides.

Run:
    python bencher/example/example_agg_over_time.py
"""

from datetime import datetime, timedelta

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


def example_agg_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
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
        run_cfg.auto_plot = i == len(time_offsets) - 1
        bench.plot_sweep(
            "agg_over_time",
            input_vars=["float1", "float2"],
            result_vars=["distance"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            aggregate=True,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_over_time, save=True)
