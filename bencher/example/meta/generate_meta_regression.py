"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"

REGRESSION_EXAMPLES = [
    "regression_percentage",
    "regression_adaptive_stable_noisy",
    "regression_adaptive_gradual_drift",
    "regression_adaptive_sudden_drop",
    "regression_adaptive_outlier_immune",
    "regression_adaptive_oscillating",
]


# Shared benchmark class used by every adaptive example. The benchmark reads
# ``_time_offset`` (per-release mean) and ``_time_noise`` (per-release sigma),
# seeded per release for reproducibility while still producing independent
# samples across repeats.
_ADAPTIVE_CLASS_CODE = '''\
class NoisyServerBenchmark(bn.ParametrizedSweep):
    """Server response time with tunable per-release mean and noise sigma."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)

    # Per-release knobs set externally before each plot_sweep call.
    _time_offset = 0.0   # shift applied to the mean response time
    _time_noise = 0.0    # sigma of gaussian noise added to each sample
    _release_seed = 0    # per-release RNG seed
    _call_counter = 0    # incremented per sample so repeats differ

    def benchmark(self):
        import random as _rnd

        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        # Deterministic-but-varied noise per call within a release.
        rng = _rnd.Random(self._release_seed * 1_000_003 + self._call_counter)
        NoisyServerBenchmark._call_counter += 1
        noise = rng.gauss(0.0, self._time_noise) if self._time_noise > 0 else 0.0
        self.response_time = base_rt + self._time_offset + noise'''


_ADAPTIVE_BODY_TEMPLATE = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=4)
run_cfg.regression_detection = True
run_cfg.regression_method = "adaptive"
run_cfg.regression_fail = False

benchable = NoisyServerBenchmark()
bench = benchable.to_bench(run_cfg)

# Per-release schedule: (mean_offset, noise_sigma) for each historical release.
schedule = {schedule!r}

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
"""


def _adaptive_schedule_stable_noisy():
    """20 releases, flat mean, high noise — user's pain point."""
    return [(0.0, 15.0) for _ in range(20)]


def _adaptive_schedule_gradual_drift():
    """20 releases, mean drifts +1ms per release, moderate noise."""
    return [(1.5 * i, 5.0) for i in range(20)]


def _adaptive_schedule_sudden_drop():
    """10 stable releases then a sudden +40ms step on the latest."""
    return [(0.0, 4.0) for _ in range(10)] + [(40.0, 4.0)]


def _adaptive_schedule_outlier_immune():
    """Stable baseline with one historical glitch at release 5."""
    schedule = [(0.0, 2.0) for _ in range(15)]
    schedule[5] = (150.0, 2.0)  # isolated bad release, later reverted
    return schedule


def _adaptive_schedule_oscillating():
    """Periodic diurnal-style pattern around a stable baseline."""
    import math

    return [(10.0 * math.sin(i * math.pi / 3.0), 2.0) for i in range(18)]


_ADAPTIVE_SCHEDULES = {
    "regression_adaptive_stable_noisy": (
        "Adaptive detection — noisy-but-stable signal (no false positive)",
        _adaptive_schedule_stable_noisy(),
    ),
    "regression_adaptive_gradual_drift": (
        "Adaptive detection — gradual long-term drift (drift test fires)",
        _adaptive_schedule_gradual_drift(),
    ),
    "regression_adaptive_sudden_drop": (
        "Adaptive detection — sudden short-term drop (step test fires)",
        _adaptive_schedule_sudden_drop(),
    ),
    "regression_adaptive_outlier_immune": (
        "Adaptive detection — isolated historical outlier ignored",
        _adaptive_schedule_outlier_immune(),
    ),
    "regression_adaptive_oscillating": (
        "Adaptive detection — oscillating periodic signal (no false positive)",
        _adaptive_schedule_oscillating(),
    ),
}


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bn.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def benchmark(self):
        if self.example == "regression_percentage":
            self._generate_percentage()
        elif self.example in _ADAPTIVE_SCHEDULES:
            self._generate_adaptive(self.example)

    def _generate_percentage(self):
        """Percentage-based regression detection over time."""
        imports = "from datetime import datetime, timedelta\n\nimport bencher as bn"
        class_code = '''\
class ServerBenchmark(bn.ParametrizedSweep):
    """A server benchmark whose response time degrades over successive releases."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)
    throughput = bn.ResultFloat(units="req/s", direction=bn.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def benchmark(self):
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        leak = 1.0 + self._time_offset * 0.12  # memory leak grows per release
        self.response_time = base_rt * leak
        self.throughput = 1000.0 / self.response_time'''
        body = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
run_cfg.regression_detection = True
run_cfg.regression_method = "percentage"
run_cfg.regression_fail = False

benchable = ServerBenchmark()
bench = benchable.to_bench(run_cfg)

# Simulate 7 server releases: stable at first, then a memory leak kicks in
releases = [0.0, 0.1, 0.0, 0.5, 1.5, 3.0, 5.0]

base_time = datetime(2024, 1, 1)
for i, offset in enumerate(releases):
    benchable._time_offset = offset
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    run_cfg.auto_plot = i == len(releases) - 1
    bench.plot_sweep(
        "regression_detection",
        input_vars=["connections", "payload_kb"],
        result_vars=["response_time", "throughput"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(seconds=i),
        aggregate=True,
    )
"""
        self.generate_example(
            title="Regression detection — percentage threshold over time",
            output_dir=OUTPUT_DIR,
            filename="example_regression_percentage",
            function_name="example_regression_percentage",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"over_time": True},
        )

    def _generate_adaptive(self, name: str) -> None:
        """Emit a single adaptive-method example file."""
        title, schedule = _ADAPTIVE_SCHEDULES[name]
        imports = "from datetime import datetime, timedelta\n\nimport bencher as bn"
        body = _ADAPTIVE_BODY_TEMPLATE.format(schedule=schedule)
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=f"example_{name}",
            function_name=f"example_{name}",
            imports=imports,
            body=body,
            class_code=_ADAPTIVE_CLASS_CODE,
            run_kwargs={"over_time": True},
        )


def example_meta_regression(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaRegression().to_bench(run_cfg)

    bench.plot_sweep(
        title="Regression Detection",
        input_vars=[bn.sweep("example", REGRESSION_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_regression)
