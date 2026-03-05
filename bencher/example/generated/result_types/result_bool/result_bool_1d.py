"""Auto-generated example: Result Bool: 1D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableBoolResult


def example_result_bool_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Bool: 1D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 3
    benchable = BenchableBoolResult()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["threshold"], result_vars=["pass_rate"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_1d)
