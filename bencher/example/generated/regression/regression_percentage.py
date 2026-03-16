"""Auto-generated example: Regression detection — percentage threshold over time."""

from typing import Any

import bencher as bch
from datetime import datetime, timedelta


class DegradingBenchmark(bch.ParametrizedSweep):
    """A benchmark whose latency degrades over successive runs."""

    latency = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="ops/s", direction=bch.OptDir.maximize)

    run_number = 0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10.0 + DegradingBenchmark.run_number * 5.0
        self.throughput = 100.0 - DegradingBenchmark.run_number * 15.0
        return super().__call__(**kwargs)


def example_regression_percentage(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Regression detection — percentage threshold over time."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 2
    run_cfg.regression_detection = True
    run_cfg.regression_method = "percentage"
    run_cfg.regression_fail = False

    bench = bch.Bench("regression_percentage", DegradingBenchmark(), run_cfg=run_cfg)

    base_time = datetime(2024, 1, 1)
    # Simulate 5 time snapshots with increasing degradation
    for i in range(5):
        DegradingBenchmark.run_number = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            input_vars=[],
            result_vars=["latency", "throughput"],
            title=f"Snapshot {i}",
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
        bench.sample_cache = None  # reset for next run

    # Print the regression report from the last result
    report = res.regression_report
    if report is not None:
        print("\n" + report.summary())
        print(f"\nRegressed variables: {[r.variable for r in report.regressed_variables]}")
    else:
        print("No regression report (need at least 2 time points)")

    return bench


if __name__ == "__main__":
    bch.run(example_regression_percentage)
