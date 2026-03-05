"""Auto-generated example: 0 Float, 1 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_with_repeats_0_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0 Float, 1 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 10
    run_cfg.level = 4
    run_cfg.over_time = False
    benchable = BenchableObject()
    benchable.noise_scale = 0.15
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["wave"],
        result_vars=["distance", "sample_noise"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_0_float_1_cat)
