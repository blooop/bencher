"""Auto-generated example: Result Video: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableVideoResult


def example_result_video_1d(run_cfg=None):
    """Result Video: 1D input."""
    bench = BenchableVideoResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["sides"], result_vars=["animation"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_video_1d, level=3)
