"""Auto-generated example: 2 Float, 0 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_2_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2 Float, 0 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 4
    run_cfg.over_time = False
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["float1", "float2"],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_2_float_0_cat)
