"""Auto-generated example: Result Dataset: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableDataSetResult


def example_result_dataset_1d(run_cfg=None):
    """Result Dataset: 1D input."""
    bench = BenchableDataSetResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["value"], result_vars=["result_ds"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_dataset_1d, level=3)
