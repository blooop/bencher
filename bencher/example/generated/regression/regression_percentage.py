"""Auto-generated example: Regression detection — percentage threshold over time."""

from datetime import datetime, timedelta

import bencher as bn


class ServerBenchmark(bn.ParametrizedSweep):
    """A server benchmark whose response time degrades over successive releases."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultVar(units="ms", direction=bn.OptDir.minimize)
    throughput = bn.ResultVar(units="req/s", direction=bn.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def benchmark(self):
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        leak = 1.0 + self._time_offset * 0.12  # memory leak grows per release
        self.response_time = base_rt * leak
        self.throughput = 1000.0 / self.response_time


def example_regression_percentage(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression detection — percentage threshold over time."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
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
            aggregate=True,
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
    bn.run(example_regression_percentage, over_time=True)
