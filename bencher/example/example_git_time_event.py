"""Example showing how to use git_time_event() for over_time sliders with date+commit labels."""

import math
import bencher as bch


class ServerLatency(bch.ParametrizedSweep):
    """Simulates server latency measurements across endpoints."""

    endpoint = bch.StringSweep(["/api/users", "/api/orders", "/api/health"], doc="API endpoint")

    latency = bch.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"/api/users": 45, "/api/orders": 120, "/api/health": 5}[self.endpoint]
        self.latency = base + 10 * math.sin(hash(self.endpoint))
        return super().__call__()


def example_git_time_event(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Track benchmark results over time using the current git commit as the time label.

    ``git_time_event()`` returns a string like ``"2024-06-15 abc1234d"`` combining the commit
    date and short hash.  Pass it as ``time_event`` with ``over_time=True`` so the slider
    shows which commit produced each data point.
    """

    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.time_event = bch.git_time_event()

    bench = ServerLatency().to_bench(run_cfg)

    bench.plot_sweep(
        title="Latency by Endpoint",
        input_vars=["endpoint"],
        result_vars=["latency"],
        description=example_git_time_event.__doc__,
        run_cfg=run_cfg,
    )
    return bench


if __name__ == "__main__":
    bch.run(example_git_time_event)
