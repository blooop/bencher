"""Auto-generated example: Max Time Events — cap over_time history."""

from typing import Any

import random
import bencher as bch
from datetime import datetime, timedelta


class LatencyMonitor(bch.ParametrizedSweep):
    """Simulates a service latency monitor that drifts over time.

    When tracking metrics over_time, history grows without bound by default.
    Setting max_time_events on BenchRunCfg caps the number of retained
    time slices, keeping only the most recent ones.
    """

    endpoint = bch.StringSweep(["/api/users", "/api/orders"], doc="API endpoint")

    latency = bch.ResultVar(units="ms", doc="Response latency")

    _drift = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"/api/users": 45, "/api/orders": 120}[self.endpoint]
        self.latency = base + self._drift + random.gauss(0, 5)
        return super().__call__()


def example_advanced_max_time_events(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Max Time Events — cap over_time history."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True

    # Keep only the 3 most recent time slices in the cache.
    # Without this, every call to plot_sweep appends a new slice and the
    # cache grows without bound.
    run_cfg.max_time_events = 3

    benchable = LatencyMonitor()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 6, 1)
    for i in range(3):
        benchable._drift = i * 3.0  # simulate gradual degradation
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            title="Service Latency",
            input_vars=["endpoint"],
            result_vars=["latency"],
            description="max_time_events caps over_time history so only the N most "
            "recent snapshots are retained, preventing unbounded cache growth.",
            run_cfg=run_cfg,
            time_src=base_time + timedelta(hours=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_advanced_max_time_events, level=3)
