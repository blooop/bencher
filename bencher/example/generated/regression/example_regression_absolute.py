"""Auto-generated example: Regression detection — hard absolute ceiling."""

from datetime import datetime, timedelta

import bencher as bn


class SlaBenchmark(bn.ParametrizedSweep):
    """SLA benchmark with a hard response-time ceiling."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)

    _time_offset = 0.0  # set externally per snapshot

    def benchmark(self):
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        self.response_time = base_rt * (1.0 + self._time_offset)


def example_regression_absolute(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression detection — hard absolute ceiling."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
    run_cfg.regression_detection = True
    # SLA: response_time must stay below 25 ms no matter what history says.
    run_cfg.regression_absolute = 25.0
    run_cfg.regression_fail = False

    benchable = SlaBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Each successive release scales response time up until the SLA ceiling is breached.
    releases = [0.0, 0.05, 0.1, 0.2, 0.4, 0.8, 1.5]

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate(releases):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == len(releases) - 1
        bench.plot_sweep(
            "regression_absolute",
            input_vars=["connections", "payload_kb"],
            result_vars=["response_time"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            aggregate=True,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_absolute, over_time=True)
