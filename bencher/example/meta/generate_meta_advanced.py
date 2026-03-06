"""Meta-generator: Advanced pattern examples.

Covers cache/context patterns, time events, and report customization —
features previously only shown in hand-written examples.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "advanced"

ADVANCED_EXAMPLES = [
    "cache_patterns",
    "time_event",
    "report_save",
]


class MetaAdvanced(MetaGeneratorBase):
    """Generate Python examples demonstrating advanced patterns."""

    example = bch.StringSweep(ADVANCED_EXAMPLES, doc="Which advanced example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "cache_patterns":
            self._generate_cache_patterns()
        elif self.example == "time_event":
            self._generate_time_event()
        elif self.example == "report_save":
            self._generate_report_save()

        return super().__call__()

    def _generate_cache_patterns(self):
        """B3: Cache and context patterns."""
        imports = "import math\nimport random\nimport bencher as bch"
        body = '''\
class NoisySensor(bch.ParametrizedSweep):
    """Simulates a sensor with configurable noise.

    Demonstrates cache_samples and run_tag usage. When cache_samples is True,
    each individual function call is cached so expensive computations are not
    repeated if the run is interrupted.
    """

    temperature = bch.FloatSweep(
        default=25.0, bounds=[0.0, 100.0], doc="Sensor temperature", units="C"
    )

    reading = bch.ResultVar(units="V", doc="Sensor voltage reading")

    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.reading = 0.5 + 0.03 * self.temperature + math.sin(self.temperature * 0.1)
        if self.noise_scale > 0:
            self.reading += random.gauss(0, self.noise_scale)
        return super().__call__()

run_cfg = run_cfg or bch.BenchRunCfg()

# run_tag partitions the cache so different experiment runs don't collide.
run_cfg.run_tag = "sensor_v1"

# cache_samples=True stores each individual call, useful for long-running
# benchmarks that might be interrupted.
run_cfg.cache_samples = True
run_cfg.clear_sample_cache = True
run_cfg.repeats = 5

bench = NoisySensor().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["temperature"],
    result_vars=["reading"],
    const_vars=dict(noise_scale=0.3),
    description="Demonstrates cache_samples and run_tag for reliable benchmarking. "
    "cache_samples=True stores every function call individually so data is not "
    "lost if the run crashes. run_tag partitions the cache between experiments.",
    post_description="The repeated measurements show noise around the true sensor "
    "curve. If this run were interrupted, re-running would reuse cached samples.",
)
'''
        self.generate_example(
            title="Cache Patterns — run_tag and cache_samples",
            output_dir=OUTPUT_DIR,
            filename="advanced_cache_patterns",
            function_name="example_advanced_cache_patterns",
            imports=imports,
            body=body,
            run_kwargs={"level": 3, "repeats": 5},
        )

    def _generate_time_event(self):
        """B7: TimeEvent example."""
        imports = "import math\nimport bencher as bch"
        body = '''\
class PullRequestBenchmark(bch.ParametrizedSweep):
    """Tracks benchmark metrics across discrete events (e.g. pull requests).

    TimeEvent lets you label each run with a string (like a PR number or
    commit hash) rather than using wall-clock time. This is useful for
    CI pipelines where you want to track performance across commits.
    """

    workload = bch.StringSweep(
        ["light", "medium", "heavy"], doc="Workload intensity"
    )

    throughput = bch.ResultVar(units="req/s", doc="Requests per second")

    _event_idx = 0  # set externally per event

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"light": 1000, "medium": 500, "heavy": 200}[self.workload]
        # Simulate gradual improvement across events
        self.throughput = base + self._event_idx * 30
        return super().__call__()

run_cfg = run_cfg or bch.BenchRunCfg()
run_cfg.over_time = True

benchable = PullRequestBenchmark()
bench = benchable.to_bench(run_cfg)

# Simulate three pull request events
events = ["PR-100-baseline", "PR-105-optimize-db", "PR-112-add-cache"]
for i, event_name in enumerate(events):
    benchable._event_idx = i
    run_cfg.time_event = event_name
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    bench.plot_sweep(
        title="PR Benchmark",
        input_vars=["workload"],
        result_vars=["throughput"],
        description="TimeEvent tracks metrics across discrete events like pull "
        "requests. Each event gets a human-readable label on the time axis "
        "instead of a timestamp.",
        run_cfg=run_cfg,
    )
'''
        self.generate_example(
            title="Time Events — track metrics across discrete events",
            output_dir=OUTPUT_DIR,
            filename="advanced_time_event",
            function_name="example_advanced_time_event",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
        )

    def _generate_report_save(self):
        """B8: Report customization and saving."""
        imports = "import math\nimport bencher as bch"
        body = '''\
class QuadraticFit(bch.ParametrizedSweep):
    """A simple quadratic function for demonstrating report features."""

    x = bch.FloatSweep(default=0, bounds=[-2, 2], doc="Input value")
    y = bch.ResultVar(units="ul", doc="Quadratic output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = self.x**2 - 1
        return super().__call__()

bench = QuadraticFit().to_bench(run_cfg)

# First sweep: standard plot
bench.plot_sweep(
    input_vars=["x"],
    result_vars=["y"],
    description="A simple quadratic curve. Each call to plot_sweep adds a new "
    "tab to the report. You can call plot_sweep multiple times with different "
    "input subsets to build a comprehensive report.",
)

# bench.report gives access to the Panel report object.
# You can append custom markdown or HTML content:
bench.report.append_markdown("## Custom Section\\n\\nYou can add **markdown** content "
    "directly to the report using `bench.report.append_markdown()`.",
    name="Custom Content")
'''
        self.generate_example(
            title="Report Customization — saving and appending content",
            output_dir=OUTPUT_DIR,
            filename="advanced_report_save",
            function_name="example_advanced_report_save",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
        )


def example_meta_advanced(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaAdvanced().to_bench(run_cfg)

    bench.plot_sweep(
        title="Advanced Patterns",
        input_vars=[bch.p("example", ADVANCED_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_advanced)
