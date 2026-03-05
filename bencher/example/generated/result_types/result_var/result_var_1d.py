"""Auto-generated example: Result Var: 1D input."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_result_var_1d(run_cfg=None):
    """Result Var: 1D input."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_var_1d, level=3)
