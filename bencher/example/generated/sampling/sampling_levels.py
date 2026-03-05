"""Auto-generated example: Sampling: Levels."""

import bencher as bch
from bencher.example.meta.example_meta import BenchMeta


def example_sampling_levels(run_cfg=None):
    """Sampling: Levels."""
    bench = BenchMeta().to_bench(run_cfg)
    bench.plot_sweep(
        title="Level-based sampling resolution",
        input_vars=[
            bch.p("float_vars", [1, 2]),
            bch.p("level", [2, 3, 4, 5]),
        ],
        const_vars=dict(categorical_vars=0),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_levels, level=3)
