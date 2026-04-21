"""Auto-generated example: Regression detection — absolute delta guard."""

from datetime import datetime, timedelta

import bencher as bn


class LatencyBenchmark(bn.ParametrizedSweep):
    """Latency benchmark with a small absolute step the delta guard catches."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)

    _time_offset = 0.0  # set externally per snapshot

    def benchmark(self):
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        # Additive ms step per release — percent change stays tiny at high
        # baselines, but the absolute delta exceeds the guard.
        self.response_time = base_rt + self._time_offset


def example_regression_delta(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression detection — absolute delta guard."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
    run_cfg.regression_detection = True
    # Loose percentage threshold to show it stays quiet, while the delta guard
    # fires on the additive ms step.
    run_cfg.regression_percentage = 20.0
    run_cfg.regression_delta = 2.0  # ms
    run_cfg.regression_fail = False

    benchable = LatencyBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Stable baseline, then a +3 ms absolute step that's under 20% but over 2 ms.
    releases = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0]

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate(releases):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == len(releases) - 1
        bench.plot_sweep(
            "regression_delta",
            input_vars=["connections", "payload_kb"],
            result_vars=["response_time"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            aggregate=True,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_delta, over_time=True)
