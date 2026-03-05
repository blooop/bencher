"""Auto-generated example: Plot Type: Line."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_line(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Line."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])
    res.to_line()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_line, level=3)
