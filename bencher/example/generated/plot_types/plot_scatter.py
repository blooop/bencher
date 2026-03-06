"""Auto-generated example: Plot Type: Scatter."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_scatter(run_cfg=None):
    """Plot Type: Scatter."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    bench.report.append(res.to_scatter())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter, level=3)
