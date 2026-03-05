"""Auto-generated example: Constant Variables: 1 fixed parameter(s)."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_1(run_cfg=None):
    """Constant Variables: 1 fixed parameter(s)."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "float2"], result_vars=["distance"], const_vars=dict(float3=0.5)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_1, level=3)
