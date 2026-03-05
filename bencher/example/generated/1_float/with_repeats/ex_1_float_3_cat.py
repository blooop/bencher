"""Auto-generated example: 1 Float, 3 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_with_repeats_1_float_3_cat(run_cfg=None):
    """1 Float, 3 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "wave", "variant", "transform"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.15),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_1_float_3_cat, level=4, repeats=10)
