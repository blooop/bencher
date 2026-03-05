"""Auto-generated example: Sampling: Custom Values."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_sampling_custom_values(run_cfg=None):
    """Sampling: Custom Values."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[bch.p("float1", [0.0, 0.1, 0.3, 0.7, 0.9, 1.0])],
        result_vars=["distance"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_custom_values, level=3)
