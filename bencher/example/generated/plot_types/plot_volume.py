"""Auto-generated example: Plot Type: Volume."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_volume(run_cfg=None):
    """Plot Type: Volume."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2", "float3"], result_vars=["distance"])
    res.to_volume()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_volume, level=2)
