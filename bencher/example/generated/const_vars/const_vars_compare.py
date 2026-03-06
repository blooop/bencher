"""Auto-generated example: Const Vars: Comparing Slices."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_compare(run_cfg=None):
    """Const Vars: Comparing Slices."""
    bench = BenchableObject().to_bench(run_cfg)
    for float2_val in [0.0, 0.5, 1.0]:
        bench.plot_sweep(
            title=f"float1 sweep with float2={float2_val}",
            input_vars=["float1"],
            result_vars=["distance"],
            const_vars=dict(float2=float2_val, float3=0.0),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_compare, level=4)
