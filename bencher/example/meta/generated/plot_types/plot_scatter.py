"""Auto-generated example: Plot Type: Scatter."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_scatter(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Scatter."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 1
    run_cfg.level = 3
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    res.to_scatter()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter)
