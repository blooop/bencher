"""Auto-generated example: Result Image: 2D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_result_image_2d(run_cfg=None):
    """Result Image: 2D input."""
    bench = BenchableImageResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["sides", "radius"], result_vars=["polygon"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_2d, level=2)
