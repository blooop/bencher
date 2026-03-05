"""Auto-generated example: 0 Float, 0 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_0_float_0_cat(run_cfg=None):
    """0 Float, 0 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=[], result_vars=["distance", "sample_noise"])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_0_float_0_cat, level=4)
