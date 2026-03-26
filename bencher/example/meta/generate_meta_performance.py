"""Meta-generator: Performance self-introspection examples.

Generates examples that benchmark bencher's own overhead, enabling
performance tracking across commits via the documentation gallery.
"""

import inspect
from typing import Any

import bencher as bn
from bencher.example.example_self_benchmark import BencherSelfBenchmark, TrivialWorkload
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "performance"

PERFORMANCE_EXAMPLES = [
    "perf_self_benchmark",
    "perf_self_benchmark_over_time",
]


class MetaPerformance(MetaGeneratorBase):
    """Generate Python examples for bencher self-introspection."""

    example = bn.StringSweep(PERFORMANCE_EXAMPLES, doc="Which performance example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "perf_self_benchmark":
            self._generate_self_benchmark()
        elif self.example == "perf_self_benchmark_over_time":
            self._generate_self_benchmark_over_time()

        return super().__call__()

    def _generate_self_benchmark(self):
        """Generate the self-benchmark example."""
        imports = "import bencher as bn"

        body = """\
bench = BencherSelfBenchmark().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["num_samples"],
    result_vars=["total_ms", "dataset_setup_ms", "job_submission_ms", "job_execution_ms"],
    title="Phase Timing vs Problem Size",
)
bench.plot_sweep(
    input_vars=["num_samples"],
    result_vars=["throughput"],
    title="Throughput vs Problem Size",
)
bench.plot_sweep(
    input_vars=["num_samples", "use_cache"],
    result_vars=["total_ms"],
    title="Cache Impact on Total Time",
)
"""

        self.generate_example(
            title="Bencher self-introspection: overhead vs problem size",
            output_dir=OUTPUT_DIR,
            filename="perf_self_benchmark",
            function_name="example_perf_self_benchmark",
            imports=imports,
            body=body,
            class_code=_get_shared_class_code(),
        )

    def _generate_self_benchmark_over_time(self):
        """Generate the over-time self-benchmark example."""
        imports = "import bencher as bn"

        body = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
run_cfg.auto_plot = False
time_src = bn.git_time_event()
bench = BencherSelfBenchmark().to_bench(run_cfg)
bench.plot_sweep(
    input_vars=["num_samples"],
    result_vars=["total_ms", "dataset_setup_ms", "job_submission_ms", "job_execution_ms"],
    title="Overhead Over Time: Phase Timing",
    time_src=time_src,
)
bench.plot_sweep(
    input_vars=["num_samples"],
    result_vars=["throughput"],
    title="Overhead Over Time: Throughput",
    time_src=time_src,
)
"""

        self.generate_example(
            title="Bencher self-introspection: overhead tracked over time",
            output_dir=OUTPUT_DIR,
            filename="perf_self_benchmark_over_time",
            function_name="example_perf_self_benchmark_over_time",
            imports=imports,
            body=body,
            class_code=_get_shared_class_code(),
            run_kwargs={"over_time": True},
        )


def _get_shared_class_code():
    """Extract class source from the canonical module to avoid duplication.

    Falls back to reading the source file directly if inspect.getsource is
    unavailable (e.g. zipapp or compiled distributions).
    """
    try:
        return inspect.getsource(TrivialWorkload) + "\n\n" + inspect.getsource(BencherSelfBenchmark)
    except OSError:
        import importlib.resources

        src = importlib.resources.files("bencher.example").joinpath("example_self_benchmark.py")
        return src.read_text(encoding="utf-8")


def example_meta_performance():
    """Generate all performance self-introspection examples."""
    gen = MetaPerformance()
    for example in PERFORMANCE_EXAMPLES:
        gen(example=example)
