"""Meta-generator: Advanced pattern examples.

Covers cache/context patterns, time events, and report customization —
features previously only shown in hand-written examples.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "advanced"

ADVANCED_EXAMPLES = [
    "cache_patterns",
    "time_event",
    "git_time_event",
    "max_time_events",
    "report_save",
    "agg_over_time",
]


class MetaAdvanced(MetaGeneratorBase):
    """Generate Python examples demonstrating advanced patterns."""

    example = bn.StringSweep(ADVANCED_EXAMPLES, doc="Which advanced example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "cache_patterns":
            self._generate_cache_patterns()
        elif self.example == "time_event":
            self._generate_time_event()
        elif self.example == "git_time_event":
            self._generate_git_time_event()
        elif self.example == "max_time_events":
            self._generate_max_time_events()
        elif self.example == "report_save":
            self._generate_report_save()
        elif self.example == "agg_over_time":
            self._generate_agg_over_time()

        return super().__call__()

    def _generate_cache_patterns(self):
        """B3: Cache and context patterns."""
        imports = "import math\nimport random\nimport bencher as bn"
        class_code = '''\
class NoisySensor(bn.ParametrizedSweep):
    """Simulates a sensor with configurable noise.

    Demonstrates cache_samples and run_tag usage. When cache_samples is True,
    each individual function call is cached so expensive computations are not
    repeated if the run is interrupted.
    """

    temperature = bn.FloatSweep(
        default=25.0, bounds=[0.0, 100.0], doc="Sensor temperature", units="C"
    )

    reading = bn.ResultVar(units="V", doc="Sensor voltage reading")

    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.reading = 0.5 + 0.03 * self.temperature + math.sin(self.temperature * 0.1)
        if self.noise_scale > 0:
            self.reading += random.gauss(0, self.noise_scale)
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bn.BenchRunCfg()

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
"""
        self.generate_example(
            title="Cache Patterns — run_tag and cache_samples",
            output_dir=OUTPUT_DIR,
            filename="advanced_cache_patterns",
            function_name="example_advanced_cache_patterns",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3, "repeats": 5},
        )

    def _generate_time_event(self):
        """B7: TimeEvent example."""
        imports = "import bencher as bn"
        class_code = '''\
class PullRequestBenchmark(bn.ParametrizedSweep):
    """Tracks benchmark metrics across discrete events (e.g. pull requests).

    TimeEvent lets you label each run with a string (like a PR number or
    commit hash) rather than using wall-clock time. This is useful for
    CI pipelines where you want to track performance across commits.
    """

    workload = bn.StringSweep(
        ["light", "medium", "heavy"], doc="Workload intensity"
    )

    throughput = bn.ResultVar(units="req/s", doc="Requests per second")

    _event_idx = 0  # set externally per event

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"light": 1000, "medium": 500, "heavy": 200}[self.workload]
        # Simulate gradual improvement across events
        self.throughput = base + self._event_idx * 30
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bn.BenchRunCfg()
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
"""
        self.generate_example(
            title="Time Events — track metrics across discrete events",
            output_dir=OUTPUT_DIR,
            filename="advanced_time_event",
            function_name="example_advanced_time_event",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_git_time_event(self):
        """Git commit time event example."""
        imports = "import bencher as bn"
        class_code = '''\
class ServerLatency(bn.ParametrizedSweep):
    """Simulates server latency measurements across endpoints.

    Use ``bn.git_time_event()`` as the ``time_src`` argument to
    ``plot_sweep`` to label each over_time slider tick with the commit
    date and short hash, e.g. ``"2024-06-15 abc1234d"``.  This lets you
    trace benchmark results back to the exact code that produced them.
    """

    endpoint = bn.StringSweep(
        ["/api/users", "/api/orders", "/api/health"], doc="API endpoint"
    )

    latency = bn.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.latency = {"/api/users": 48, "/api/orders": 125, "/api/health": 8}[self.endpoint]
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bn.BenchRunCfg()
run_cfg.over_time = True

bench = ServerLatency().to_bench(run_cfg)

# git_time_event() returns a string like "2024-06-15 abc1234d".
# Pass it as time_src so each commit gets its own slider tick.
bench.plot_sweep(
    title="Latency by Endpoint",
    input_vars=["endpoint"],
    result_vars=["latency"],
    description="Demonstrates git_time_event() for labelling over_time "
    "slider ticks with the commit date and short hash.",
    run_cfg=run_cfg,
    time_src=bn.git_time_event(),
)
"""
        self.generate_example(
            title="Git Time Event — date + commit hash slider labels",
            output_dir=OUTPUT_DIR,
            filename="advanced_git_time_event",
            function_name="example_advanced_git_time_event",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_max_time_events(self):
        """Demonstrate max_time_events to cap over_time history."""
        imports = "import random\nimport bencher as bn\nfrom datetime import datetime, timedelta"
        class_code = '''\
class LatencyMonitor(bn.ParametrizedSweep):
    """Simulates a service latency monitor that drifts over time.

    When tracking metrics over_time, history grows without bound by default.
    Setting max_time_events on BenchRunCfg caps the number of retained
    time slices, keeping only the most recent ones.
    """

    endpoint = bn.StringSweep(
        ["/api/users", "/api/orders"], doc="API endpoint"
    )

    latency = bn.ResultVar(units="ms", doc="Response latency")

    _drift = 0.0  # set externally per snapshot

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"/api/users": 45, "/api/orders": 120}[self.endpoint]
        self.latency = base + self._drift + random.gauss(0, 5)
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bn.BenchRunCfg()
run_cfg.over_time = True

# Keep only the 3 most recent time slices in the cache.
# Without this, every call to plot_sweep appends a new slice and the
# cache grows without bound.
run_cfg.max_time_events = 3

benchable = LatencyMonitor()
bench = benchable.to_bench(run_cfg)

# Run 5 iterations but only keep the 3 most recent thanks to max_time_events.
# Without the cap, all 5 time slices would accumulate in the cache.
base_time = datetime(2024, 6, 1)
for i in range(5):
    benchable._drift = i * 3.0  # simulate gradual degradation
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    bench.plot_sweep(
        title="Service Latency",
        input_vars=["endpoint"],
        result_vars=["latency"],
        description="5 snapshots are recorded but max_time_events=3 trims the oldest, "
        "so only the 3 most recent are retained.",
        run_cfg=run_cfg,
        time_src=base_time + timedelta(hours=i),
    )
"""
        self.generate_example(
            title="Max Time Events — cap over_time history",
            output_dir=OUTPUT_DIR,
            filename="advanced_max_time_events",
            function_name="example_advanced_max_time_events",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_report_save(self):
        """B8: Report customization and saving."""
        imports = "import bencher as bn"
        class_code = '''\
class QuadraticFit(bn.ParametrizedSweep):
    """A simple quadratic function for demonstrating report features."""

    x = bn.FloatSweep(default=0, bounds=[-2, 2], doc="Input value")
    y = bn.ResultVar(units="ul", doc="Quadratic output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.y = self.x**2 - 1
        return super().__call__()'''
        body = """\
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
"""
        self.generate_example(
            title="Report Customization — saving and appending content",
            output_dir=OUTPUT_DIR,
            filename="advanced_report_save",
            function_name="example_advanced_report_save",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_agg_over_time(self):
        """Aggregate a 2D sweep down to a scalar curve over time with error bounds."""
        imports = "import math\nimport bencher as bn\nfrom datetime import datetime, timedelta"
        class_code = '''\
class ThermalPlate(bn.ParametrizedSweep):
    """Measures temperature across a 2D plate that cools over time.

    A 2D sweep (x, y) is run at each time snapshot. Both dimensions are
    then collapsed via aggregate=True, producing a single mean +/- std per
    time point. The curve shows how the plate-wide average temperature
    decays, with error bounds from the spatial variation across the grid.
    """

    x = bn.FloatSweep(
        default=0.5, bounds=[0.0, 1.0], doc="Horizontal position on plate"
    )
    y = bn.FloatSweep(
        default=0.5, bounds=[0.0, 1.0], doc="Vertical position on plate"
    )

    temperature = bn.ResultVar(units="C", doc="Measured temperature")

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # Hot spot at centre, decaying over time
        self.temperature = (
            100 * math.sin(math.pi * self.x) * math.sin(math.pi * self.y)
            * math.exp(-0.3 * self._time_offset)
            + 20
        )
        return super().__call__()'''
        body = """\
run_cfg = run_cfg or bn.BenchRunCfg()
run_cfg.over_time = True

benchable = ThermalPlate()
bench = benchable.to_bench(run_cfg)

base_time = datetime(2024, 1, 1)
time_offsets = [0.0, 1.0, 2.0, 3.0, 4.0]
for i, offset in enumerate(time_offsets):
    benchable._time_offset = offset
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    run_cfg.auto_plot = i == len(time_offsets) - 1
    bench.plot_sweep(
        "thermal_plate",
        input_vars=["x", "y"],
        result_vars=["temperature"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(seconds=i),
        aggregate=True,
    )
"""
        self.generate_example(
            title="Aggregate Over Time — 2D sweep to scalar curve with error bounds",
            output_dir=OUTPUT_DIR,
            filename="advanced_agg_over_time",
            function_name="example_advanced_agg_over_time",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 4},
        )


def example_meta_advanced(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaAdvanced().to_bench(run_cfg)

    bench.plot_sweep(
        title="Advanced Patterns",
        input_vars=[bn.p("example", ADVANCED_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_advanced)
