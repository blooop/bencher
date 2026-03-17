"""Auto-generated example: Regression detection — percentage threshold over time."""

from typing import Any

import bencher as bch
from datetime import datetime, timedelta


class ServerBenchmark(bch.ParametrizedSweep):
    """A server benchmark whose response time degrades over successive releases."""

    connections = bch.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bch.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bch.ResultVar(units="ms", direction=bch.OptDir.minimize)
    throughput = bch.ResultVar(units="req/s", direction=bch.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        leak = 1.0 + self._time_offset * 0.12  # memory leak grows per release
        self.response_time = base_rt * leak
        self.throughput = 1000.0 / self.response_time
        return super().__call__()


def example_regression_percentage(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Regression detection — percentage threshold over time."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 2
    run_cfg.regression_detection = True
    run_cfg.regression_method = "percentage"
    run_cfg.regression_fail = False

    benchable = ServerBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Simulate 7 server releases: stable at first, then a memory leak kicks in
    releases = [0.0, 0.1, 0.0, 0.5, 1.5, 3.0, 5.0]

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate(releases):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == len(releases) - 1
        bench.plot_sweep(
            "regression_detection",
            input_vars=["connections", "payload_kb"],
            result_vars=["response_time", "throughput"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            agg_over_dims=["connections", "payload_kb"],
        )

    # Regression report
    res = bench.results[-1]
    report = res.regression_report
    if report is not None:
        print("\n" + report.summary())
        regressed = [r.variable for r in report.regressed_variables]
        if regressed:
            lines = [report.summary(), "", f"Regressed variables: {regressed}"]
            bench.report.append_markdown("\n".join(lines), name="Regression Report")

    return bench


if __name__ == "__main__":
    bch.run(example_regression_percentage)
