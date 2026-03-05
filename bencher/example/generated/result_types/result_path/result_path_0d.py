"""Auto-generated example: Result Path: 0D input."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchablePathResult


def example_result_path_0d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Path: 0D input."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    benchable = BenchablePathResult()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["content"], result_vars=["file_result"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_path_0d, level=3)
