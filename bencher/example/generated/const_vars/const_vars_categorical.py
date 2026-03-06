"""Auto-generated example: Const Vars: Fixing Categorical Parameters."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_const_vars_categorical(run_cfg=None):
    """Const Vars: Fixing Categorical Parameters."""
    bench = BenchableObject().to_bench(run_cfg)
    bench.plot_sweep(
        title="Sweep float1 x variant, with wave fixed to False",
        input_vars=["float1", "variant"],
        result_vars=["distance"],
        const_vars=dict(wave=False),
    )
    bench.plot_sweep(
        title="Sweep float1 x variant, with wave fixed to True",
        input_vars=["float1", "variant"],
        result_vars=["distance"],
        const_vars=dict(wave=True),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_categorical, level=4)
