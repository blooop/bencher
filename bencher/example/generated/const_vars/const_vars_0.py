"""Auto-generated example: Constant Variables: 0 fixed parameter(s)."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_0(run_cfg=None):
    """Constant Variables: 0 fixed parameter(s)."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["float1", "float2", "float3"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_0, level=3)
