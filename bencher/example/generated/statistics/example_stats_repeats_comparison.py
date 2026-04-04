"""Auto-generated example: Repeats Comparison: 1 vs 5 vs 20 repeats on a categorical sweep."""

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


def example_stats_repeats_comparison(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Repeats Comparison: 1 vs 5 vs 20 repeats on a categorical sweep."""
    bench = BenchableObject().to_bench(run_cfg)
    for n_repeats in [1, 5, 20]:
        noise = 0.3 if n_repeats > 1 else 0.0
        sweep_cfg = bn.BenchRunCfg()
        sweep_cfg.level = 3
        sweep_cfg.repeats = n_repeats
        bench.plot_sweep(
            title=f"{n_repeats} repeat(s)",
            input_vars=["wave"],
            result_vars=["distance"],
            const_vars=dict(noise_scale=noise),
            run_cfg=sweep_cfg,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_stats_repeats_comparison)
