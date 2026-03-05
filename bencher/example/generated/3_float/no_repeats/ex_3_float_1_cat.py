"""Auto-generated example: 3 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_3_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """3 Float, 1 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=[
            "float1",
            "float2",
            {"name": "float3", "values": None, "max_level": 3, "samples": None},
            "wave",
        ],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_3_float_1_cat, level=4)
