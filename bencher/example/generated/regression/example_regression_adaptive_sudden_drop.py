"""Auto-generated example: Adaptive detection — sudden short-term drop (step test fires)."""

from datetime import datetime, timedelta

import bencher as bn


class NoisyServerBenchmark(bn.ParametrizedSweep):
    """Server response time with tunable per-release mean and noise sigma."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)

    # Per-release knobs set externally before each plot_sweep call.
    _time_offset = 0.0  # shift applied to the mean response time
    _time_noise = 0.0  # sigma of gaussian noise added to each sample
    _release_seed = 0  # per-release RNG seed
    _call_counter = 0  # incremented per sample so repeats differ

    def benchmark(self):
        import random as _rnd

        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        rng = _rnd.Random(self._release_seed * 1_000_003 + self._call_counter)
        type(self)._call_counter += 1
        noise = rng.gauss(0.0, self._time_noise) if self._time_noise > 0 else 0.0
        self.response_time = base_rt + self._time_offset + noise


def example_regression_adaptive_sudden_drop(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detection — sudden short-term drop (step test fires)."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=4)
    run_cfg.regression_detection = True
    run_cfg.regression_method = "adaptive"
    run_cfg.regression_fail = False

    benchable = NoisyServerBenchmark()
    bench = benchable.to_bench(run_cfg)

    # Per-release schedule: (mean_offset, noise_sigma) for each historical release.
    schedule = [
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (0.0, 4.0),
        (40.0, 4.0),
    ]

    base_time = datetime(2024, 1, 1)
    for i, (offset, sigma) in enumerate(schedule):
        benchable._time_offset = offset
        benchable._time_noise = sigma
        benchable._release_seed = i + 1
        type(benchable)._call_counter = 0
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == len(schedule) - 1
        bench.plot_sweep(
            "regression_detection",
            input_vars=["connections", "payload_kb"],
            result_vars=["response_time"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            aggregate=True,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_adaptive_sudden_drop, over_time=True)
