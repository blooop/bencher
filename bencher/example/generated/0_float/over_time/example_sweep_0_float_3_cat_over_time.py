"""Auto-generated example: 0 Float, 3 Categorical (over time)."""

import random
import bencher as bn
from datetime import datetime, timedelta


class DeploymentConfig(bn.ParametrizedSweep):
    """Full config matrix: protocol, region, and log level."""

    protocol = bn.StringSweep(["http", "grpc"], doc="Network protocol")
    region = bn.StringSweep(["us-east", "eu-west", "ap-south"], doc="Deployment region")
    log_level = bn.StringSweep(["debug", "info", "warn"], doc="Logging level")

    throughput = bn.ResultFloat(units="req/s", doc="Request throughput")

    _time_offset = 0.0

    def benchmark(self):
        proto_factor = {"http": 1.0, "grpc": 1.8}[self.protocol]
        region_base = {"us-east": 500, "eu-west": 420, "ap-south": 350}[self.region]
        log_penalty = {"debug": 0.7, "info": 1.0, "warn": 1.0}[self.log_level]
        self.throughput = region_base * proto_factor * log_penalty + random.gauss(0, 0.1 * 50)
        self.throughput += self._time_offset * 10


def example_sweep_0_float_3_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 3 Categorical (over time)."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
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
            description="A 0 float + 3 categorical parameter sweep tracked over time. Setting over_time=True records multiple time snapshots that can be scrubbed via a slider. Each call to plot_sweep with a new time_src appends a snapshot to the history. This is designed for nightly benchmarks or CI pipelines where you want to track how metrics evolve across commits, releases, or environmental changes. Use clear_history=True on the first snapshot to reset, and clear_cache=True to force re-evaluation. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
            post_description="The time slider lets you scrub through snapshots. The 'All Time Points (aggregated)' tab pools all snapshots into one view, smoothing out per-snapshot noise to reveal long-term trends.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_3_cat_over_time, level=4, over_time=True)
