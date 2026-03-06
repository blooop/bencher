"""Auto-generated example: Plot Type: Heatmap."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_heatmap(run_cfg=None):
    """Plot Type: Heatmap."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2"], result_vars=["distance"])
    bench.report.append(res.to_heatmap())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_heatmap, level=2)
