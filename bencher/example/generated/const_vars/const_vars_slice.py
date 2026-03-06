"""Auto-generated example: Const Vars: Slicing a 3D Space."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_slice(run_cfg=None):
    """Const Vars: Slicing a 3D Space."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1", "float2"], result_vars=["distance"], const_vars=dict(float3=0.5)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_slice, level=3)
