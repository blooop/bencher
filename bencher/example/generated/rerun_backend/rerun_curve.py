"""Auto-generated example: Rerun Backend: Rerun Curve."""

import bencher as bn
from bencher.example.meta.example_meta import BenchableObject


def example_rerun_curve(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Backend: Rerun Curve."""
    bench = BenchableObject().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["float1"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to_rerun())

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_curve, level=3, repeats=5)
