"""Auto-generated example: 0 Float, 3 Categorical."""

from typing import Any

import bencher as bch
from datetime import datetime, timedelta


class DeploymentConfig(bch.ParametrizedSweep):
    """Full config matrix: protocol, region, and log level."""

    protocol = bch.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bch.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")
    log_level = bch.StringSweep(["debug", "info", "warn"], doc="Logging level")

    throughput = bch.ResultVar(units="req/s", doc="Request throughput")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        log_penalty = {"debug": 0.7, "info": 1.0, "warn": 1.0}[self.log_level]
        self.throughput = region_base * proto_factor * log_penalty + __import__("random").gauss(
            0, 0.15 * 50
        )
        self.throughput += self._time_offset * 10
        return super().__call__()


def example_over_time_repeats_0_float_3_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0 Float, 3 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
    benchable = DeploymentConfig()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["protocol", "region", "log_level"],
            result_vars=["throughput"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bch.run(example_over_time_repeats_0_float_3_cat, level=4)
