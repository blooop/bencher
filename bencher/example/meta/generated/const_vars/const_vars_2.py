"""Auto-generated example: Constant Variables: 2 fixed parameter(s)."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_2(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Constant Variables: 2 fixed parameter(s)."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 3
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["float1"], result_vars=["distance"], const_vars=dict(float2=0.5, float3=0.5)
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_2)
