"""Auto-generated example: Composable Dataset: ComposeType.overlay."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableDataSetResult


def example_composable_dataset_overlay(run_cfg=None):
    """Composable Dataset: ComposeType.overlay."""
    bench = BenchableDataSetResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["value"], result_vars=["result_ds"])

    return bench


if __name__ == "__main__":
    bch.run(example_composable_dataset_overlay, level=3)
