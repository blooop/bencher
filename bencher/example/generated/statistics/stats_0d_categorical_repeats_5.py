"""Auto-generated example: Statistics: 5 repeat(s), categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_0d_categorical_repeats_5(run_cfg=None):
    """Statistics: 5 repeat(s), categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["wave"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_stats_0d_categorical_repeats_5, level=3, repeats=5)
