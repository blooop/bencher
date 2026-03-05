"""Auto-generated example: Result Path: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchablePathResult


def example_result_path_1d(run_cfg=None):
    """Result Path: 1D input."""
    bench = BenchablePathResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["content"], result_vars=["file_result"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_path_1d, level=3)
