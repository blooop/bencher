"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks.
"""

import inspect
import math
from dataclasses import dataclass

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"


# Real class that backs every adaptive example. Defined at module level so
# ``inspect.getsource`` can capture its definition verbatim as the ``class_code``
# embedded in each generated example. The class is never instantiated here.
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


_ADAPTIVE_CLASS_CODE = inspect.getsource(NoisyServerBenchmark)


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


@dataclass(frozen=True)
class AdaptiveExample:
    """Title + schedule for an adaptive-method example file.

    ``schedule`` is a list of ``(mean_offset, noise_sigma)`` tuples, one entry
    per historical release.
    """

    title: str
    schedule: list[tuple[float, float]]


_ADAPTIVE_EXAMPLES: dict[str, AdaptiveExample] = {
    "regression_adaptive_stable_noisy": AdaptiveExample(
        title="Adaptive detection — noisy-but-stable signal (no false positive)",
        schedule=[(0.0, 15.0)] * 20,
    ),
    "regression_adaptive_gradual_drift": AdaptiveExample(
        title="Adaptive detection — gradual long-term drift (drift test fires)",
        schedule=[(1.5 * i, 5.0) for i in range(20)],
    ),
    "regression_adaptive_sudden_drop": AdaptiveExample(
        title="Adaptive detection — sudden short-term drop (step test fires)",
        schedule=[(0.0, 4.0) for _ in range(10)] + [(40.0, 4.0)],
    ),
    "regression_adaptive_outlier_immune": AdaptiveExample(
        title="Adaptive detection — isolated historical outlier ignored",
        schedule=[(150.0, 2.0) if i == 5 else (0.0, 2.0) for i in range(15)],
    ),
    "regression_adaptive_oscillating": AdaptiveExample(
        title="Adaptive detection — oscillating periodic signal (no false positive)",
        schedule=[(10.0 * math.sin(i * math.pi / 3.0), 2.0) for i in range(18)],
    ),
}


REGRESSION_EXAMPLES = ["regression_percentage", *_ADAPTIVE_EXAMPLES.keys()]


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bn.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def benchmark(self):
        if self.example == "regression_percentage":
            self._generate_percentage()
            return

        adaptive = _ADAPTIVE_EXAMPLES.get(self.example)
        if adaptive is not None:
            self._generate_adaptive(self.example, adaptive)

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

    def _generate_adaptive(self, name: str, adaptive: AdaptiveExample) -> None:
        """Emit a single adaptive-method example file."""
        imports = "from datetime import datetime, timedelta\n\nimport bencher as bn"
        body = _ADAPTIVE_BODY_TEMPLATE.format(schedule=adaptive.schedule)
        self.generate_example(
            title=adaptive.title,
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
