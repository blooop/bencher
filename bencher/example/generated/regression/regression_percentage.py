"""Auto-generated example: Regression detection — percentage threshold over time."""

from typing import Any

import bencher as bch
from datetime import datetime, timedelta


class DegradingBenchmark(bch.ParametrizedSweep):
    """A benchmark whose latency degrades over successive runs."""

    latency = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="ops/s", direction=bch.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.latency = 10.0 + self._time_offset * 5.0
        self.throughput = 100.0 - self._time_offset * 15.0
        return super().__call__()


def example_regression_percentage(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Regression detection — percentage threshold over time."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 2
    run_cfg.regression_detection = True
    run_cfg.regression_method = "percentage"
    run_cfg.regression_fail = False

    benchable = DegradingBenchmark()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate([0.0, 1.0, 2.0, 3.0, 4.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = False
        bench.plot_sweep(
            "regression_detection",
            input_vars=[],
            result_vars=["latency", "throughput"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )

    res = bench.results[-1]

    # Append auto plots from the final accumulated result (all 5 time points)
    bench.report.append(res.to_auto_plots())

    report = res.regression_report
    if report is not None:
        print("\n" + report.summary())
        print(f"\nRegressed variables: {[r.variable for r in report.regressed_variables]}")

    return bench


if __name__ == "__main__":
    bch.run(example_regression_percentage)
