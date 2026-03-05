"""Auto-generated example: Plot Type: Curve."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_curve(run_cfg=None):
    """Plot Type: Curve."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["float1"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    res.to_curve()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_curve, level=3, repeats=5)
