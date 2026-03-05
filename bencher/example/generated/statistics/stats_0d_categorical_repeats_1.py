"""Auto-generated example: Statistics: 1 repeat(s), categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_0d_categorical_repeats_1(run_cfg=None):
    """Statistics: 1 repeat(s), categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_stats_0d_categorical_repeats_1, level=3)
