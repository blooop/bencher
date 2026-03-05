"""Auto-generated example: Result Bool: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableBoolResult


def example_result_bool_0d(run_cfg=None):
    """Result Bool: 0D input."""
    bench = BenchableBoolResult().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["difficulty"], result_vars=["pass_rate"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_0d, level=3)
