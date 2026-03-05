"""Auto-generated example: Result Bool: 2D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableBoolResult


def example_result_bool_2d(run_cfg=None):
    """Result Bool: 2D input."""
    bench = BenchableBoolResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["threshold", "difficulty"], result_vars=["pass_rate"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_2d, level=2)
