"""Auto-generated example: Result String: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableStringResult


def example_result_string_0d(run_cfg=None):
    """Result String: 0D input."""
    bench = BenchableStringResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["label"], result_vars=["report"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_string_0d, level=3)
