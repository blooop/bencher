"""Auto-generated example: Statistics: 5 repeat(s), 1D float."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_1d_float_repeats_5(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Statistics: 5 repeat(s), 1D float."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 5
    run_cfg.level = 3
    benchable = BenchableObject()
    benchable.noise_scale = 0.15
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_stats_1d_float_repeats_5)
