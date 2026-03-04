"""Auto-generated example: 0 Float, 3 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_no_repeats_0_float_3_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0 Float, 3 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 4
    run_cfg.over_time = False
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["wave", "variant", "transform"],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_0_float_3_cat)
