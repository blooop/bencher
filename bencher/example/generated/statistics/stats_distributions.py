"""Auto-generated example: Distributions: box-whisker and scatter-jitter for categorical sweeps."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_distributions(run_cfg=None):
    """Distributions: box-whisker and scatter-jitter for categorical sweeps."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["wave", "variant"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.3),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_stats_distributions, level=3, repeats=20)
