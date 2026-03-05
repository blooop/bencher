"""Auto-generated example: 1 Float, 0 Categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_with_repeats_1_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1 Float, 0 Categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 10
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["float1"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.15),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_1_float_0_cat, level=4)
