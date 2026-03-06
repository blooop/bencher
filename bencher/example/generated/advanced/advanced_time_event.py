"""Auto-generated example: Time Events — track metrics across discrete events."""

import bencher as bch


class PullRequestBenchmark(bch.ParametrizedSweep):
    """Tracks benchmark metrics across discrete events (e.g. pull requests).

    TimeEvent lets you label each run with a string (like a PR number or
    commit hash) rather than using wall-clock time. This is useful for
    CI pipelines where you want to track performance across commits.
    """

    workload = bch.StringSweep(["light", "medium", "heavy"], doc="Workload intensity")

    throughput = bch.ResultVar(units="req/s", doc="Requests per second")

    _event_idx = 0  # set externally per event

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"light": 1000, "medium": 500, "heavy": 200}[self.workload]
        # Simulate gradual improvement across events
        self.throughput = base + self._event_idx * 30
        return super().__call__()


def example_advanced_time_event(run_cfg=None):
    """Time Events — track metrics across discrete events."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True

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
    bch.run(example_advanced_time_event, level=3)
