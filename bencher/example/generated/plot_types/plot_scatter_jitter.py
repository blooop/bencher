"""Auto-generated example: Plot Type: Scatter Jitter."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)


def example_plot_scatter_jitter(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Scatter Jitter."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 10
    run_cfg.level = 3
    benchable = BenchableObject()
    benchable.noise_scale = 0.15
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    res.to(ScatterJitterResult)

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter_jitter)
