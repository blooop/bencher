"""Auto-generated example: 2 Float, 2 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_with_repeats_2_float_2_cat(run_cfg=None):
    """2 Float, 2 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "float2", "wave", "variant"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.15),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_2_float_2_cat, level=4, repeats=3)
