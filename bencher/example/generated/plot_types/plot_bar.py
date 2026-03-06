"""Auto-generated example: Plot Type: Bar."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_bar(run_cfg=None):
    """Plot Type: Bar."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    bench.report.append(res.to_bar())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_bar, level=3)
