"""Auto-generated example: Result String: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableStringResult


def example_result_string_1d(run_cfg=None):
    """Result String: 1D input."""
    bench = BenchableStringResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["label", "value"], result_vars=["report"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_string_1d, level=3)
