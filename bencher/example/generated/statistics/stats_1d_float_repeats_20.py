"""Auto-generated example: Statistics: 20 repeat(s), 1D float."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_1d_float_repeats_20(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Statistics: 20 repeat(s), 1D float."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 20
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_stats_1d_float_repeats_20, level=3)
