"""Example demonstrating benchmark regression detection.

Simulates a web server benchmarked across concurrent connections and payload
size. Over successive releases a memory leak degrades response times and
throughput. The first releases are stable, then performance degrades until
metrics clearly exceed acceptable bounds. Shows several time snapshots (heatmap
slider and aggregated trend curve) so the regression is visually obvious.
"""

from datetime import datetime, timedelta
from typing import Any

import bencher as bn


class ServerBenchmark(bn.ParametrizedSweep):
    """A server benchmark whose response time degrades over successive releases."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultVar(units="ms", direction=bn.OptDir.minimize)
    throughput = bn.ResultVar(units="req/s", direction=bn.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        leak = 1.0 + self._time_offset * 0.12  # memory leak grows per release
        self.response_time = base_rt * leak
        self.throughput = 1000.0 / self.response_time
        return super().__call__()


def example_regression(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Run a benchmark with regression detection over several time snapshots.

    Stable releases are followed by progressively worse degradation so the
    aggregated trend curve clearly shows when metrics go outside bounds.
    """
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
    run_cfg.over_time = True
    run_cfg.regression_detection = True
    run_cfg.regression_method = "percentage"
    run_cfg.regression_fail = False

    benchable = ServerBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Simulate 7 server releases: stable at first, then a memory leak kicks in
    # offset 0 = baseline performance; higher offset = worse leak
    releases = [
        0.0,  # v1.0 — baseline
        0.1,  # v1.1 — stable
        0.0,  # v1.2 — stable
        0.5,  # v1.3 — small degradation begins
        1.5,  # v1.4 — leak worsens
        3.0,  # v1.5 — clearly outside bounds
        5.0,  # v1.6 — severe regression
    ]

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate(releases):
        benchable._time_offset = offset  # pylint: disable=protected-access
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
            lines = [report.summary(), "", f"**Regressed variables:** {regressed}"]
            bench.report.append_markdown("\n".join(lines), name="Regression Report")
        else:
            bench.report.append_markdown(report.summary(), name="Regression Report")

    return bench


if __name__ == "__main__":
    bn.run(example_regression, save=True)
