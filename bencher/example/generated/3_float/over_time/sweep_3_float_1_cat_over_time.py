"""Auto-generated example: 3 Float, 1 Categorical (over time)."""

import random
import math
import bencher as bn
from datetime import datetime, timedelta


class HashComparison(bn.ParametrizedSweep):
    """Hash throughput across key size, payload, iterations, and algorithm."""

    key_size = bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")
    algorithm = bn.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")

    throughput = bn.ResultVar(units="MB/s", doc="Hash throughput")

    _time_offset = 0.0

    def benchmark(self):
        algo_speed = {"sha256": 1.0, "blake2": 1.4, "md5": 1.8}[self.algorithm]
        self.throughput = (
            algo_speed
            * 500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        self.throughput += random.gauss(0, 0.1 * 30)
        self.throughput += self._time_offset * 10


def example_sweep_3_float_1_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """3 Float, 1 Categorical (over time)."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = HashComparison()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=["key_size", "payload_size", "iterations", "algorithm"],
            result_vars=["throughput"],
            description="A 3 float + 1 categorical parameter sweep tracked over time. Setting over_time=True records multiple time snapshots that can be scrubbed via a slider. Each call to plot_sweep with a new time_src appends a snapshot to the history. This is designed for nightly benchmarks or CI pipelines where you want to track how metrics evolve across commits, releases, or environmental changes. Use clear_history=True on the first snapshot to reset, and clear_cache=True to force re-evaluation. A 3D float sweep produces a volumetric representation. This is useful for visualising scalar fields in 3D parameter spaces.",
            post_description="The time slider lets you scrub through snapshots. The 'All Time Points (aggregated)' tab pools all snapshots into one view, smoothing out per-snapshot noise to reveal long-term trends.",
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_3_float_1_cat_over_time, level=4, over_time=True)
