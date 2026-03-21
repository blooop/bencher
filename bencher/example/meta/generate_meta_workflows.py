"""Meta-generator: Workflow examples.

Demonstrates BenchRunner, multiple sweeps per report, and the InputCfg/OutputCfg
separation pattern — features that only existed in manual examples until now.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "workflows"

WORKFLOW_EXAMPLES = [
    "bench_runner",
    "multi_sweep_report",
    "input_output_cfg",
]


class MetaWorkflows(MetaGeneratorBase):
    """Generate Python examples demonstrating workflow patterns."""

    example = bn.StringSweep(WORKFLOW_EXAMPLES, doc="Which workflow example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "bench_runner":
            self._generate_bench_runner()
        elif self.example == "multi_sweep_report":
            self._generate_multi_sweep()
        elif self.example == "input_output_cfg":
            self._generate_input_output_cfg()

        return super().__call__()

    def _generate_bench_runner(self):
        """B1: BenchRunner example showing multiple benchmarks combined."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
class SineWave(bn.ParametrizedSweep):
    """A sine wave — one of two benchmarks combined by BenchRunner."""

    theta = bn.FloatSweep(default=0, bounds=[0, math.pi], doc="Input angle", units="rad")
    out_sin = bn.ResultVar(units="V", doc="Sine output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__()'''
        body = """\
# This example shows the building block that BenchRunner orchestrates.
# To combine multiple independent benchmarks into one session, use:
#
#   runner = bn.BenchRunner("comparison")
#   runner.add(sine_benchmark_fn)    # each fn returns a Bench
#   runner.add(cosine_benchmark_fn)
#   runner.run(level=3)              # runs all, collects reports
#
# BenchRunner is useful when you have separate benchmark functions
# that you want to run together and compare side by side.

bench = SineWave().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["theta"],
    result_vars=["out_sin"],
    description="BenchRunner lets you manage multiple benchmark functions in a "
    "single session. Each added function produces its own tab in the combined "
    "report. This example shows one such benchmark function.",
)
"""
        self.generate_example(
            title="BenchRunner — run multiple benchmarks in one session",
            output_dir=OUTPUT_DIR,
            filename="workflow_bench_runner",
            function_name="example_workflow_bench_runner",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_multi_sweep(self):
        """B2: Multiple sweeps per report."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
class DataPipeline(bn.ParametrizedSweep):
    """Simulates a data processing pipeline with configurable stages."""

    batch_size = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Batch size", units="rows")
    parallelism = bn.FloatSweep(default=4, bounds=[1, 16], doc="Worker threads")
    storage = bn.StringSweep(["ssd", "hdd", "network"], doc="Storage backend")

    throughput = bn.ResultVar(units="rows/s", doc="Processing throughput")
    latency = bn.ResultVar(units="ms", doc="Per-batch latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        storage_factor = {"ssd": 1.0, "hdd": 0.4, "network": 0.25}[self.storage]
        self.throughput = self.batch_size * math.sqrt(self.parallelism) * storage_factor * 0.5
        self.latency = 1000 * self.batch_size / max(self.throughput, 1)
        return super().__call__()'''
        body = """\
bench = DataPipeline().to_bench(run_cfg)

# Sweep 1: Vary only batch_size — produces a 1D line plot
bench.plot_sweep(
    title="Batch Size Sweep",
    input_vars=["batch_size"],
    result_vars=["throughput", "latency"],
    description="Sweep the batch size while keeping other parameters at defaults. "
    "This shows how batch size affects both throughput and latency.",
)

# Sweep 2: Vary batch_size and parallelism — produces a 2D heatmap
bench.plot_sweep(
    title="Batch Size + Parallelism Sweep",
    input_vars=["batch_size", "parallelism"],
    result_vars=["throughput"],
    description="Sweep both batch size and parallelism to see their combined effect "
    "on throughput. The heatmap reveals optimal configurations.",
)

# Sweep 3: Compare storage backends at fixed configuration
bench.plot_sweep(
    title="Storage Backend Comparison",
    input_vars=["storage"],
    result_vars=["latency"],
    const_vars=dict(batch_size=500, parallelism=4),
    description="Compare latency across storage backends at a fixed configuration. "
    "const_vars pins batch_size and parallelism so only storage varies.",
)
"""
        self.generate_example(
            title="Multiple Sweeps — progressive report with tabs",
            output_dir=OUTPUT_DIR,
            filename="workflow_multi_sweep",
            function_name="example_workflow_multi_sweep",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )

    def _generate_input_output_cfg(self):
        """B9: InputCfg/OutputCfg separation pattern."""
        imports = "import math\nimport bencher as bn"
        class_code = '''\
class ServerMetrics(bn.ParametrizedSweep):
    """Output metrics from the server benchmark."""

    throughput = bn.ResultVar(
        units="req/s", direction=bn.OptDir.maximize, doc="Request throughput"
    )
    latency = bn.ResultVar(
        units="ms", direction=bn.OptDir.minimize, doc="Response latency"
    )


class ServerConfig(bn.ParametrizedSweep):
    """Server configuration parameters.

    The static bench_function method takes a ServerConfig instance and
    returns a ServerMetrics instance. This separation makes it clear
    which variables are inputs and which are outputs.
    """

    worker_count = bn.FloatSweep(
        default=4, bounds=[1, 32], doc="Number of worker threads"
    )
    cache_size = bn.StringSweep(
        ["small", "medium", "large"], doc="Cache tier size"
    )

    @staticmethod
    def bench_function(cfg: "ServerConfig") -> ServerMetrics:
        """Simulate a server benchmark with the given configuration."""
        output = ServerMetrics()
        size_factor = {"small": 0.7, "medium": 1.0, "large": 1.3}[cfg.cache_size]
        output.throughput = 100 * math.sqrt(cfg.worker_count) * size_factor
        output.latency = 500 / max(output.throughput, 1)
        return output'''
        body = """\
# The Bench constructor accepts the static function and the ServerConfig class.
# This is an alternative to the ParametrizedSweep.__call__ pattern.
bench = bn.Bench("input_output_example", ServerConfig.bench_function, ServerConfig, run_cfg)
bench.plot_sweep(
    input_vars=[ServerConfig.param.worker_count],
    result_vars=[ServerMetrics.param.throughput, ServerMetrics.param.latency],
    description="The InputCfg/OutputCfg pattern separates input parameters from "
    "result metrics into distinct classes. The benchmark function is a static "
    "method on ServerConfig that returns a ServerMetrics instance.",
)
bench.plot_sweep(
    input_vars=[ServerConfig.param.worker_count, ServerConfig.param.cache_size],
    result_vars=[ServerMetrics.param.throughput],
    description="A 2D sweep combining a continuous and categorical input. "
    "Each cache size produces a different throughput curve over worker counts.",
)
"""
        self.generate_example(
            title="InputCfg/OutputCfg — separated input and output classes",
            output_dir=OUTPUT_DIR,
            filename="workflow_input_output_cfg",
            function_name="example_workflow_input_output_cfg",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )


def example_meta_workflows(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaWorkflows().to_bench(run_cfg)

    bench.plot_sweep(
        title="Workflow Patterns",
        input_vars=[bn.p("example", WORKFLOW_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_workflows)
