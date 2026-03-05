"""Auto-generated example: Plot Type: Image."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_plot_image(run_cfg=None):
    """Plot Type: Image."""
    bench = BenchableImageResult().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["sides"], result_vars=["polygon"])
    res.to_panes()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_image, level=3)
