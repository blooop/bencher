"""Auto-generated example: Const Vars: Setting Non-Default Configuration."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_noise(run_cfg=None):
    """Const Vars: Setting Non-Default Configuration."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "float2"],
        result_vars=["distance", "sample_noise"],
        const_vars=dict(noise_scale=0.3),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_noise, level=3)
