"""Example showing how to use git_time_event() for over_time sliders with date+commit labels."""

import bencher as bn


class ServerLatency(bn.ParametrizedSweep):
    """Simulates server latency measurements across endpoints."""

    endpoint = bn.StringSweep(["/api/users", "/api/orders", "/api/health"], doc="API endpoint")

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = {"/api/users": 48, "/api/orders": 125, "/api/health": 8}[self.endpoint]
        return super().__call__()


def example_git_time_event(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Track benchmark results over time using the current git commit as the time label.

    ``git_time_event()`` returns a string like ``"2024-06-15 14:59 abc1234d"`` combining
    wall-clock time and short hash.  Pass it as ``time_src`` to ``plot_sweep`` so the slider
    shows which run and commit produced each data point.
    """

    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.over_time = True

    bench = ServerLatency().to_bench(run_cfg)

    bench.plot_sweep(
        title="Latency by Endpoint",
        input_vars=["endpoint"],
        result_vars=["latency"],
        description=example_git_time_event.__doc__,
        run_cfg=run_cfg,
        time_src=bn.git_time_event(),
    )
    return bench


if __name__ == "__main__":
    bn.run(example_git_time_event)
