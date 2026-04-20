"""Auto-generated example: Rerun Regression — detect controller degradation over time."""

from datetime import datetime, timedelta

import bencher as bn
from bencher.example.example_rerun_over_time import ControlSystemSweep


def example_rerun_regression(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Rerun Regression — detect controller degradation over time."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    run_cfg.regression_detection = True
    run_cfg.regression_fail = False

    benchable = ControlSystemSweep()
    bench = benchable.to_bench(run_cfg)
    base_time = datetime(2024, 1, 1)

    # 3 calibration runs: stable, stable, then controller tuning degrades
    degradations = [0.0, 0.0, 0.4]
    for i, deg in enumerate(degradations):
        benchable._degradation = deg
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "controller_monitoring",
            input_vars=[],
            result_vars=["out_overshoot", "out_settling_time", "out_rerun"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(days=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_rerun_regression, over_time=True)
