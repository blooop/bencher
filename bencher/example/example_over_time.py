"""Standalone example demonstrating the over_time HoloMap slider with a 1D float sweep.

Run locally to verify interactive slider behavior:
    python bencher/example/example_over_time.py

Each time snapshot shifts the sine wave by a different phase, so the curve should
visibly change when moving the slider.
"""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_over_time(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Demo: over_time slider with 1D float sweep showing phase-shifted sine curves."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)

    time_offsets = [0.0, 0.5, 1.0, 1.5, 2.0]
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "over_time",
            input_vars=["float1"],
            result_vars=["distance"],
            run_cfg=run_cfg,
        )

    return bench


if __name__ == "__main__":
    example_over_time().report.show()
