"""Auto-generated example: Result Video: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableVideoResult


def example_result_video_0d(run_cfg=None):
    """Result Video: 0D input."""
    bench = BenchableVideoResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["speed"], result_vars=["animation"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_video_0d, level=3)
