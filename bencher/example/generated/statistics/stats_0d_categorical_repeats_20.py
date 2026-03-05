"""Auto-generated example: Statistics: 20 repeat(s), categorical."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_0d_categorical_repeats_20(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Statistics: 20 repeat(s), categorical."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 20
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["wave"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_stats_0d_categorical_repeats_20, level=3)
