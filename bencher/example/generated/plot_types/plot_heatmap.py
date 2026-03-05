"""Auto-generated example: Plot Type: Heatmap."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_plot_heatmap(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Heatmap."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["float1", "float2"], result_vars=["distance"])
    res.to_heatmap()

    return bench


if __name__ == "__main__":
    bch.run(example_plot_heatmap, level=2)
