"""Auto-generated example: Result Image: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_result_image_0d(run_cfg=None):
    """Result Image: 0D input."""
    bench = BenchableImageResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["color"], result_vars=["polygon"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_0d, level=3)
