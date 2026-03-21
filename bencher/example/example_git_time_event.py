"""Example showing over_time sliders with simulated timestamped runs.

Simulates server latency that drifts upward over successive runs and has per-call
noise.  The "All Time Points (aggregated)" tab pools every snapshot into a single
plot so the distribution is smoother than any individual time point.

In production you would pass ``time_src=bch.git_time_event()`` to label each run
with the current date and git commit hash.  Here we synthesise timestamps so the
example is self-contained and reproducible without a real git history.
"""

import random
from datetime import datetime, timedelta

import bencher as bch

# Base latencies that will be shifted by a time-dependent trend
_BASE_LATENCY = {"/api/users": 48.0, "/api/orders": 125.0, "/api/health": 8.0}


class ServerLatency(bch.ParametrizedSweep):
    """Simulates server latency measurements across endpoints with noise and drift."""

    endpoint = bch.StringSweep(["/api/users", "/api/orders", "/api/health"], doc="API endpoint")

    latency = bch.ResultVar(units="ms", doc="Response latency")

    # Plain attribute (not a param sweep variable) — set per-run by the example harness
    drift = 0.0

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = _BASE_LATENCY[self.endpoint]
        noise = random.gauss(0, 0.10 * base)  # ~10 % relative noise
        self.latency = base + self.drift * base + noise
        return super().__call__()


def example_git_time_event(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Track benchmark results over time with timestamped runs.

    Simulates five successive runs with increasing latency drift so the trend
    is visible when scrubbing the time slider.  Repeats add per-call Gaussian
    noise — switch to the **All Time Points (aggregated)** tab to see the
    distribution built from every snapshot's samples.

    In a real workflow, pass ``time_src=bch.git_time_event()`` to label each
    run with the current date and short git hash.
    """

    random.seed(42)
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 5

    benchable = ServerLatency()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime.now()
    # Simulate 5 successive "git runs" with increasing latency drift
    for i in range(5):
        benchable.drift = 0.05 * i  # 0 %, 5 %, 10 %, 15 %, 20 % uplift
        time_label = (base_time + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        bench.plot_sweep(
            title="Latency by Endpoint",
            input_vars=["endpoint"],
            result_vars=["latency"],
            description=example_git_time_event.__doc__,
            run_cfg=run_cfg,
            time_src=time_label,
            aggregate=True,
        )
    return bench


if __name__ == "__main__":
    bch.run(example_git_time_event, save=True)
