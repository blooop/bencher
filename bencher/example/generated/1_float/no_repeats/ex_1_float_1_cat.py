"""Auto-generated example: 1 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_1_float_1_cat(run_cfg=None):
    """1 Float, 1 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["float1", "wave"], result_vars=["distance", "sample_noise"])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_1_float_1_cat, level=4)
