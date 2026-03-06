"""Meta-generator: Workflow examples.

Demonstrates BenchRunner, multiple sweeps per report, and the InputCfg/OutputCfg
separation pattern — features that only existed in manual examples until now.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "workflows"

WORKFLOW_EXAMPLES = [
    "bench_runner",
    "multi_sweep_report",
    "input_output_cfg",
]


class MetaWorkflows(MetaGeneratorBase):
    """Generate Python examples demonstrating workflow patterns."""

    example = bch.StringSweep(WORKFLOW_EXAMPLES, doc="Which workflow example to generate")

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
        imports = "import math\nimport bencher as bch"
        body = '''\
class SineWave(bch.ParametrizedSweep):
    """A sine wave — one of two benchmarks combined by BenchRunner."""

    theta = bch.FloatSweep(default=0, bounds=[0, math.pi], doc="Input angle", units="rad")
    out_sin = bch.ResultVar(units="V", doc="Sine output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__()

# This example shows the building block that BenchRunner orchestrates.
# To combine multiple independent benchmarks into one session, use:
#
#   runner = bch.BenchRunner("comparison")
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
'''
        self.generate_example(
            title="BenchRunner — run multiple benchmarks in one session",
            output_dir=OUTPUT_DIR,
            filename="workflow_bench_runner",
            function_name="example_workflow_bench_runner",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
        )

    def _generate_multi_sweep(self):
        """B2: Multiple sweeps per report."""
        imports = (
            "import bencher as bch\n"
            "from bencher.example.meta.benchable_objects import BenchableRobotArm"
        )
        body = """\
bench = BenchableRobotArm().to_bench(run_cfg)

# Sweep 1: Vary only joint1 — produces a 1D line plot
bench.plot_sweep(
    title="Joint 1 Sweep",
    input_vars=["joint1"],
    result_vars=["reach", "energy"],
    description="Sweep the shoulder joint angle while keeping the elbow fixed. "
    "This shows how a single joint affects both reach and energy.",
)

# Sweep 2: Vary joint1 and joint2 — produces a 2D heatmap
bench.plot_sweep(
    title="Joint 1 + Joint 2 Sweep",
    input_vars=["joint1", "joint2"],
    result_vars=["reach"],
    description="Sweep both joint angles to see their combined effect on reach. "
    "The heatmap reveals the arm's reachable workspace.",
)

# Sweep 3: Compare gripper types at a fixed pose
bench.plot_sweep(
    title="Gripper Comparison",
    input_vars=["gripper"],
    result_vars=["energy"],
    const_vars=dict(joint1=1.0, joint2=0.8),
    description="Compare energy consumption across gripper types at a fixed arm pose. "
    "const_vars pins the joint angles so only the gripper varies.",
)
"""
        self.generate_example(
            title="Multiple Sweeps — progressive report with tabs",
            output_dir=OUTPUT_DIR,
            filename="workflow_multi_sweep",
            function_name="example_workflow_multi_sweep",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
        )

    def _generate_input_output_cfg(self):
        """B9: InputCfg/OutputCfg separation pattern."""
        imports = "import math\nimport bencher as bch"
        body = '''\
class OutputMetrics(bch.ParametrizedSweep):
    """Output metrics returned by the benchmark function.

    Separating outputs into their own class makes the interface explicit:
    the benchmark function accepts an InputConfig and returns OutputMetrics.
    """

    accuracy = bch.ResultVar(
        units="%", direction=bch.OptDir.maximize, doc="Model accuracy"
    )
    latency = bch.ResultVar(
        units="ms", direction=bch.OptDir.minimize, doc="Inference latency"
    )


class InputConfig(bch.ParametrizedSweep):
    """Input parameters for the benchmark.

    The static bench_function method takes an InputConfig instance and
    returns an OutputMetrics instance. This separation makes it clear
    which variables are inputs and which are outputs.
    """

    batch_size = bch.FloatSweep(
        default=32, bounds=[1, 128], doc="Training batch size"
    )
    model_size = bch.StringSweep(
        ["small", "medium", "large"], doc="Model architecture size"
    )

    @staticmethod
    def bench_function(cfg: "InputConfig") -> OutputMetrics:
        """Simulate training with the given configuration."""
        output = OutputMetrics()
        size_factor = {"small": 0.7, "medium": 1.0, "large": 1.3}[cfg.model_size]
        output.accuracy = 60 + 20 * math.log2(cfg.batch_size + 1) / 7 * size_factor
        output.latency = 10 * size_factor + 0.5 * cfg.batch_size
        return output

# The Bench constructor accepts the static function and the InputConfig class.
# This is an alternative to the ParametrizedSweep.__call__ pattern.
bench = bch.Bench("input_output_example", InputConfig.bench_function, InputConfig, run_cfg)
bench.plot_sweep(
    input_vars=[InputConfig.param.batch_size],
    result_vars=[OutputMetrics.param.accuracy, OutputMetrics.param.latency],
    description="The InputCfg/OutputCfg pattern separates input parameters from "
    "result metrics into distinct classes. The benchmark function is a static "
    "method on InputCfg that returns an OutputCfg instance.",
)
bench.plot_sweep(
    input_vars=[InputConfig.param.batch_size, InputConfig.param.model_size],
    result_vars=[OutputMetrics.param.accuracy],
    description="A 2D sweep combining a continuous and categorical input. "
    "Each model size produces a different accuracy curve over batch sizes.",
)
'''
        self.generate_example(
            title="InputCfg/OutputCfg — separated input and output classes",
            output_dir=OUTPUT_DIR,
            filename="workflow_input_output_cfg",
            function_name="example_workflow_input_output_cfg",
            imports=imports,
            body=body,
            run_kwargs={"level": 3},
        )


def example_meta_workflows(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaWorkflows().to_bench(run_cfg)

    bench.plot_sweep(
        title="Workflow Patterns",
        input_vars=[bch.p("example", WORKFLOW_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_workflows)
