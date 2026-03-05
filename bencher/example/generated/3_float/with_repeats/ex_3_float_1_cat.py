"""Auto-generated example: 3 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_with_repeats_3_float_1_cat(run_cfg=None):
    """3 Float, 1 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[
            "float1",
            "float2",
            {"name": "float3", "values": None, "max_level": 3, "samples": None},
            "wave",
        ],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.15),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_3_float_1_cat, level=4, repeats=3)
