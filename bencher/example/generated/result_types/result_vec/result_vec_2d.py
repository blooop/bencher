"""Auto-generated example: Result Vec: 2D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableVecResult


def example_result_vec_2d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Vec: 2D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchableVecResult()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["x", "y"], result_vars=["position"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_vec_2d, level=2)
