"""Example demonstrating benchmark regression detection.

Simulates a benchmark with intentionally degrading performance over multiple
time snapshots. Shows how regression detection identifies the degradation
and reports it.
"""

from datetime import datetime, timedelta

import bencher as bch


class DegradingBenchmark(bch.ParametrizedSweep):
    """A benchmark whose 'latency' degrades over successive runs."""

    latency = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="ops/s", direction=bch.OptDir.maximize)

    # Counter shared across calls in each run
    run_number = 0

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # latency increases each run (regression for minimize)
        self.latency = 10.0 + DegradingBenchmark.run_number * 5.0
        # throughput decreases each run (regression for maximize)
        self.throughput = 100.0 - DegradingBenchmark.run_number * 15.0
        return super().__call__(**kwargs)


def example_regression(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Run a benchmark with regression detection over 5 time snapshots."""
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    run_cfg.over_time = True
    run_cfg.repeats = 2
    run_cfg.regression_detection = True
    run_cfg.regression_method = "percentage"
    run_cfg.regression_fail = False
    run_cfg.auto_plot = False
    run_cfg.headless = True

    bench = bch.Bench("example_regression", DegradingBenchmark(), run_cfg=run_cfg)

    base_time = datetime(2024, 1, 1)
    # Simulate 5 time snapshots with increasing degradation
    for i in range(5):
        DegradingBenchmark.run_number = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            plot_callbacks=False,
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )
        bench.sample_cache = None  # reset for next run

    # Access the regression report from the last result
    report = res.regression_report
    if report is not None:
        print("\n" + report.summary())
        print(f"\nRegressed variables: {[r.variable for r in report.regressed_variables]}")
    else:
        print("No regression report (need at least 2 time points)")

    return bench


if __name__ == "__main__":
    example_regression()
