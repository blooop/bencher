"""Auto-generated example: 2 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_2_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 1 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["float1", "float2", "wave"],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_2_float_1_cat, level=4)
