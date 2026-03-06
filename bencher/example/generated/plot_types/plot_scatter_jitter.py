"""Auto-generated example: Plot Type: Scatter Jitter."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)


def example_plot_scatter_jitter(run_cfg=None):
    """Plot Type: Scatter Jitter."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["wave"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to(ScatterJitterResult))

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter_jitter, level=3, repeats=10)
