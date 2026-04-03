"""Auto-generated example: Rerun Backend: Rerun 1D Cat."""

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


def example_rerun_1d_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Backend: Rerun 1D Cat."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    bench.report.append(res.to_rerun())

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_1d_cat, level=3)
