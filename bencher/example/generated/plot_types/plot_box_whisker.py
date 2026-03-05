"""Auto-generated example: Plot Type: Box Whisker."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult


def example_plot_box_whisker(run_cfg=None):
    """Plot Type: Box Whisker."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["wave"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    res.to(BoxWhiskerResult)

    return bench


if __name__ == "__main__":
    bch.run(example_plot_box_whisker, level=3, repeats=10)
