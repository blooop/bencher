"""Auto-generated example: Sampling: Uniform."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_sampling_uniform(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Sampling: Uniform."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.level = 4
    benchable = BenchableObject()
    bench = benchable.to_bench(run_cfg)
    bench.plot_sweep(input_vars=["float1"], result_vars=["distance"])

    return bench


if __name__ == "__main__":
    bch.run(example_sampling_uniform)
