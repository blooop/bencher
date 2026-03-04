"""Standalone example demonstrating the over_time HoloMap slider at 0D, 1D, and 2D.

Run locally to verify interactive slider behavior:
    python bencher/example/example_over_time.py

Each time snapshot shifts the sine wave by a different phase, so the plots should
visibly change when moving the slider.
"""

from datetime import datetime, timedelta

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def _run_over_time(bench, benchable, run_cfg, input_vars, title, result_vars=None):
    """Helper: run several time snapshots for a single sweep configuration.

    All intermediate snapshots disable plotting. Only the final result (which
    has the full accumulated history) is manually added to the report.

    Explicit time_src values are passed to simulate realistic usage where
    plot_sweep calls are naturally spaced apart in time.
    """
    if result_vars is None:
        result_vars = ["distance"]
    time_offsets = [0.0, 0.5, 1.0, 1.5, 2.0]
    base_time = datetime(2000, 1, 1)
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset  # pylint: disable=protected-access
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = False
        bench.plot_sweep(
            title,
            input_vars=input_vars,
            result_vars=result_vars,
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
    bench.report.append_result(bench.results[-1])


def example_over_time_0D(run_cfg: bch.BenchRunCfg | None = None, report=None) -> bch.Bench:
    """Demo: over_time with 0 input vars — produces a time-series line chart."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg, report=report)
    _run_over_time(bench, benchable, run_cfg, input_vars=[], title="over_time 0D")
    return bench


def example_over_time_1D(run_cfg: bch.BenchRunCfg | None = None, report=None) -> bch.Bench:
    """Demo: over_time with 1 float input — slider scrubs through phase-shifted curves."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg, report=report)
    _run_over_time(bench, benchable, run_cfg, input_vars=["float1"], title="over_time 1D")
    return bench


def example_over_time_2D(run_cfg: bch.BenchRunCfg | None = None, report=None) -> bch.Bench:
    """Demo: over_time with 2 float inputs — slider scrubs through 2D heatmaps."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg, report=report)
    _run_over_time(bench, benchable, run_cfg, input_vars=["float1", "float2"], title="over_time 2D")
    return bench


def example_over_time_3D(run_cfg: bch.BenchRunCfg | None = None, report=None) -> bch.Bench:
    """Demo: over_time with 3 float inputs — slider scrubs through 3D heatmaps."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.level = 4

    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg, report=report)
    _run_over_time(
        bench, benchable, run_cfg, input_vars=["float1", "float2", "float3"], title="over_time 3D"
    )
    return bench


def example_over_time(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Run all over_time dimensionalities (0D, 1D, 2D) and combine into one report."""
    bench = example_over_time_0D(run_cfg)
    report = bench.report
    example_over_time_1D(run_cfg, report=report)
    example_over_time_2D(run_cfg, report=report)
    # example_over_time_3D(run_cfg, report=report)
    return bench


if __name__ == "__main__":
    main_bench = example_over_time()
    main_bench.report.save_index()
    # main_bench.report.show()
