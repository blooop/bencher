"""Auto-generated example: Result Bool: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableBoolResult


def example_result_bool_0d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Bool: 0D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 3
    benchable = BenchableBoolResult()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["difficulty"], result_vars=["pass_rate"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_0d)
