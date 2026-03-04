"""Auto-generated example: Result String: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableStringResult


def example_result_string_0d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result String: 0D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 3
    benchable = BenchableStringResult()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["label"], result_vars=["report"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_string_0d)
