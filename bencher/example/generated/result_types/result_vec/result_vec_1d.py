"""Auto-generated example: Result Vec: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableVecResult


def example_result_vec_1d(run_cfg=None):
    """Result Vec: 1D input."""
    bench = BenchableVecResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["x"], result_vars=["position"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_vec_1d, level=3)
