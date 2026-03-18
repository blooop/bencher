"""Auto-generated example: Error Bands: mean +/- std deviation on a 1D sweep with 10 repeats."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_stats_error_bands(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Error Bands: mean +/- std deviation on a 1D sweep with 10 repeats."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.3),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_stats_error_bands, level=4, repeats=10)
