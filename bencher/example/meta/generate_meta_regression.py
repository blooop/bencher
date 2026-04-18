"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks, including scenario examples that
visualise the time-series data the detector operates on.
"""

from dataclasses import dataclass

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"


@dataclass(frozen=True)
class ScenarioSpec:
    """Per-scenario config for an over-time regression detection example.

    Each scenario generates a ParametrizedSweep class with a single
    ``ResultFloat`` that follows a characteristic time-series pattern,
    making the data fed to the adaptive detector directly visible.
    """

    classname: str
    doc: str
    benchmark_body: str  # body of benchmark(); continuation lines pre-indented 8 spaces
    n_steps: int = 20
    extra_imports: str = "import random"


_SCENARIOS: dict[str, ScenarioSpec] = {
    "stable_noisy": ScenarioSpec(
        classname="StableNoisyMetric",
        doc="Stable metric with Gaussian noise — no regression expected.",
        benchmark_body="self.metric_value = 100.0 + random.gauss(0, 5.0)",
    ),
    "sudden_drop": ScenarioSpec(
        classname="SuddenDropMetric",
        doc="Metric jumps at step 15 — step regression expected.",
        benchmark_body=(
            "base = 100.0 if self._step < 15 else 130.0\n"
            "        self.metric_value = base + random.gauss(0, 5.0)"
        ),
    ),
    "gradual_drift": ScenarioSpec(
        classname="GradualDriftMetric",
        doc="Metric drifts upward over time — drift regression expected.",
        benchmark_body="self.metric_value = 100.0 + 1.5 * self._step + random.gauss(0, 5.0)",
    ),
}


_SCENARIO_CLASS_TEMPLATE = '''\
class {classname}(bn.ParametrizedSweep):
    """{doc}"""

    metric_value = bn.ResultFloat(units="units", direction=bn.OptDir.minimize)

    _step = 0  # set externally per time point

    def benchmark(self):
        {benchmark_body}'''


_SCENARIO_BODY_TEMPLATE = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)
run_cfg.regression_detection = True
run_cfg.regression_method = "adaptive"
run_cfg.regression_fail = False

benchable = {classname}()
bench = benchable.to_bench(run_cfg)

base_time = datetime(2024, 1, 1)
for i in range({n_steps}):
    benchable._step = i
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    run_cfg.auto_plot = i == {n_steps} - 1
    bench.plot_sweep(
        "{scenario}",
        input_vars=[],
        result_vars=["metric_value"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(seconds=i),
    )
"""


REGRESSION_EXAMPLES = [
    "regression_percentage",
    *[f"regression_{scenario}" for scenario in _SCENARIOS],
]


def _render_scenario_class(spec: ScenarioSpec) -> str:
    return _SCENARIO_CLASS_TEMPLATE.format(
        classname=spec.classname,
        doc=spec.doc,
        benchmark_body=spec.benchmark_body,
    ).rstrip("\n")


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bn.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def benchmark(self):
        if self.example == "regression_percentage":
            self._generate_percentage_over_time()
            return

        for scenario, spec in _SCENARIOS.items():
            if self.example == f"regression_{scenario}":
                self._generate_scenario(scenario, spec)
                return

    def _generate_percentage_over_time(self):
        """End-to-end over_time example that trips the percentage detector."""
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

    def _generate_scenario(self, scenario: str, spec: ScenarioSpec) -> None:
        """Emit an over-time scenario example showing the detector's input data."""
        title = f"Regression scenario — {scenario.replace('_', ' ')}"

        stdlib_imports = ["from datetime import datetime, timedelta"]
        if spec.extra_imports:
            stdlib_imports.extend(spec.extra_imports.split("\n"))
        imports = "\n".join(stdlib_imports) + "\n\nimport bencher as bn"

        class_code = _render_scenario_class(spec)
        body = _SCENARIO_BODY_TEMPLATE.format(
            classname=spec.classname,
            n_steps=spec.n_steps,
            scenario=scenario,
        )
        filename = f"example_regression_{scenario}"
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=filename,
            imports=imports,
            body=body,
            class_code=class_code,
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
