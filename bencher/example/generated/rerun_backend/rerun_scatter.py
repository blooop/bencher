"""Auto-generated example: Rerun Backend: Rerun Scatter."""

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject


def example_rerun_scatter(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Rerun Backend: Rerun Scatter."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["wave"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to_rerun())

    return bench


if __name__ == "__main__":
    bch.run(example_rerun_scatter, level=3, repeats=10)
