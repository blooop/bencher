"""Auto-generated example: 0 Float, 1 Categorical (over time)."""

import random
import bencher as bn
from datetime import datetime, timedelta


class CacheBackend(bn.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bn.ResultVar(units="ms", doc="Cache lookup latency")

    _time_offset = 0.0

    def benchmark(self):
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base + random.gauss(0, 0.1 * base)
        self.latency += self._time_offset * 10


def example_sweep_0_float_1_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 1 Categorical (over time)."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = CacheBackend()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["backend"],
            result_vars=["latency"],
            description="A 0 float + 1 categorical parameter sweep tracked over time. Setting over_time=True records multiple time snapshots that can be scrubbed via a slider. Each call to plot_sweep with a new time_src appends a snapshot to the history. This is designed for nightly benchmarks or CI pipelines where you want to track how metrics evolve across commits, releases, or environmental changes. Use clear_history=True on the first snapshot to reset, and clear_cache=True to force re-evaluation. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
            post_description="The time slider lets you scrub through snapshots. The 'All Time Points (aggregated)' tab pools all snapshots into one view, smoothing out per-snapshot noise to reveal long-term trends.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_1_cat_over_time, level=4, over_time=True)
