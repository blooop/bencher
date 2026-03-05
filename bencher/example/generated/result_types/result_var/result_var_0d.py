"""Auto-generated example: Result Var: 0D input."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_result_var_0d(run_cfg=None):
    """Result Var: 0D input."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_var_0d, level=3)
