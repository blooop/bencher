"""Auto-generated example: Time Events — track metrics across discrete events."""

import bencher as bn


class PullRequestBenchmark(bn.ParametrizedSweep):
    """Tracks benchmark metrics across discrete events (e.g. pull requests).

    TimeEvent lets you label each run with a string (like a PR number or
    commit hash) rather than using wall-clock time. This is useful for
    CI pipelines where you want to track performance across commits.
    """

    workload = bn.StringSweep(["light", "medium", "heavy"], doc="Workload intensity")

    throughput = bn.ResultVar(units="req/s", doc="Requests per second")

    _event_idx = 0  # set externally per event

    def benchmark(self):
        base = {"light": 1000, "medium": 500, "heavy": 200}[self.workload]
        # Simulate gradual improvement across events
        self.throughput = base + self._event_idx * 30


def example_advanced_time_event(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Time Events — track metrics across discrete events."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()

    benchable = PullRequestBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Simulate three pull request events
    events = ["PR-100-baseline", "PR-105-optimize-db", "PR-112-add-cache"]
    for i, event_name in enumerate(events):
        benchable._event_idx = i
        run_cfg.time_event = event_name
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            title="PR Benchmark",
            input_vars=["workload"],
            result_vars=["throughput"],
            description="TimeEvent tracks metrics across discrete events like pull "
            "requests. Each event gets a human-readable label on the time axis "
            "instead of a timestamp.",
            run_cfg=run_cfg,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_time_event, level=3, over_time=True)
