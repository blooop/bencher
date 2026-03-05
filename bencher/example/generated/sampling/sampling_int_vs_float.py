"""Auto-generated example: Sampling: Int Vs Float."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableIntFloat


def example_sampling_int_vs_float(run_cfg=None):
    """Sampling: Int Vs Float."""
    bench = BenchableIntFloat().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["int_input", "float_input"], result_vars=["output"])

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_int_vs_float, level=3)
