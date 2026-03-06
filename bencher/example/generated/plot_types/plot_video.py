"""Auto-generated example: Plot Type: Video."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableVideoResult


def example_plot_video(run_cfg=None):
    """Plot Type: Video."""
    bench = BenchableVideoResult().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["sides"], result_vars=["animation"])
    bench.report.append(res.to_panes())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_video, level=3)
