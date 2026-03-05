"""Auto-generated example: Result Dataset: 2D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableDataSetResult


def example_result_dataset_2d(run_cfg=None):
    """Result Dataset: 2D input."""
    bench = BenchableDataSetResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["value", "scale"], result_vars=["result_ds"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_dataset_2d, level=2)
