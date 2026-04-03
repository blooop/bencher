"""Auto-generated example: Rerun Backend: Rerun 2D Float."""

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


def example_rerun_2d_float(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Backend: Rerun 2D Float."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2"], result_vars=["distance"])
    bench.report.append(res.to_rerun())

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_2d_float, level=2)
