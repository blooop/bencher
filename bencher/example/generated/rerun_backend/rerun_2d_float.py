"""Auto-generated example: Rerun Backend: Rerun 2D Float."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_rerun_2d_float(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Rerun Backend: Rerun 2D Float."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2"], result_vars=["distance"])
    bench.report.append(res.to_rerun())

    return bench


if __name__ == "__main__":
    bch.run(example_rerun_2d_float, level=2)
