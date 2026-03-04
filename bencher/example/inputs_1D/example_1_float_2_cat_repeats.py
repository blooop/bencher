"""This file demonstrates benchmarking with both float and categorical variables with repeats."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_1_float_2_cat_repeats(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    # Configure and run a benchmark with multiple input types and repeats
    run_cfg.repeats = 20
    run_cfg.level = 4
    benchable = BenchableObject()
    benchable.noise_scale = 0.15
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "wave", "variant"], result_vars=["distance", "sample_noise"]
    )
    return bench


if __name__ == "__main__":
    bch.run(example_1_float_2_cat_repeats)
