"""Auto-generated example: Plot Type: Box Whisker."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult


def example_plot_box_whisker(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Box Whisker."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 10
    run_cfg.level = 3
    benchable = BenchableObject()
    benchable.noise_scale = 0.15
    bench = benchable.to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["wave"], result_vars=["distance"])
    res.to(BoxWhiskerResult)

    return bench


if __name__ == "__main__":
    bch.run(example_plot_box_whisker)
