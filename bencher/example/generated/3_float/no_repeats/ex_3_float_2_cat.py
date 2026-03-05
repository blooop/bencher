"""Auto-generated example: 3 Float, 2 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_3_float_2_cat(run_cfg=None):
    """3 Float, 2 Categorical."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[
            "float1",
            "float2",
            {"name": "float3", "values": None, "max_level": 3, "samples": None},
            "wave",
            "variant",
        ],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_3_float_2_cat, level=4)
