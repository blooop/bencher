"""Auto-generated example: Git Time Event — date + commit hash slider labels."""

from typing import Any

import bencher as bn


class ServerLatency(bn.ParametrizedSweep):
    """Simulates server latency measurements across endpoints.

    Use ``bn.git_time_event()`` as the ``time_src`` argument to
    ``plot_sweep`` to label each over_time slider tick with the commit
    date and short hash, e.g. ``"2024-06-15 abc1234d"``.  This lets you
    trace benchmark results back to the exact code that produced them.
    """

    endpoint = bn.StringSweep(["/api/users", "/api/orders", "/api/health"], doc="API endpoint")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.latency = {"/api/users": 48, "/api/orders": 125, "/api/health": 8}[self.endpoint]
        return super().__call__()


def example_advanced_git_time_event(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Git Time Event — date + commit hash slider labels."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
    run_cfg.over_time = True

    bench = ServerLatency().to_bench(run_cfg)

    # git_time_event() returns a string like "2024-06-15 abc1234d".
    # Pass it as time_src so each commit gets its own slider tick.
    bench.plot_sweep(
        title="Latency by Endpoint",
        input_vars=["endpoint"],
        result_vars=["latency"],
        description="Demonstrates git_time_event() for labelling over_time "
        "slider ticks with the commit date and short hash.",
        run_cfg=run_cfg,
        time_src=bn.git_time_event(),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_git_time_event, level=3)
