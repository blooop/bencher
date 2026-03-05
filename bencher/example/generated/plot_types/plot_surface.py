"""Auto-generated example: Plot Type: Surface."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_surface(run_cfg=None):
    """Plot Type: Surface."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2"], result_vars=["distance"])
    res.to_surface()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_surface, level=2)
