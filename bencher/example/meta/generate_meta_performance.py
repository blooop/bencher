"""Meta-generator: Performance self-introspection examples.

Generates examples that benchmark bencher's own overhead, enabling
performance tracking across commits via the documentation gallery.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "performance"

PERFORMANCE_EXAMPLES = [
    "self_benchmark",
]


class MetaPerformance(MetaGeneratorBase):
    """Generate Python examples for bencher self-introspection."""

    example = bch.StringSweep(PERFORMANCE_EXAMPLES, doc="Which performance example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "self_benchmark":
            self._generate_self_benchmark()

        return super().__call__()

    def _generate_self_benchmark(self):
        """Generate the self-benchmark example."""
        imports = "import bencher as bch"
        class_code = '''\
class TrivialWorkload(bch.ParametrizedSweep):
    """A near-zero-cost worker so we measure framework overhead, not compute."""

    x = bch.FloatSweep(default=0, bounds=[0, 1], samples=2)
    result = bch.ResultVar(units="v", doc="trivial output")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.x * 2
        return super().__call__(**kwargs)


class BencherSelfBenchmark(bch.ParametrizedSweep):
    """Sweep over problem sizes and measure bencher's own timing phases."""

    num_samples = bch.IntSweep(
        default=10,
        bounds=[2, 100],
        samples=6,
        doc="Number of parameter samples in the inner sweep",
    )
    use_cache = bch.BoolSweep(default=False, doc="Whether sample caching is enabled")

    # Result variables - one per timing phase
    total_ms = bch.ResultVar(units="ms", doc="Total sweep wall-clock time")
    dataset_setup_ms = bch.ResultVar(units="ms", doc="Dataset initialization time")
    job_submission_ms = bch.ResultVar(units="ms", doc="Job creation and submission time")
    job_execution_ms = bch.ResultVar(units="ms", doc="Worker execution and result storage time")
    cache_check_ms = bch.ResultVar(units="ms", doc="Benchmark cache lookup time")
    sample_cache_init_ms = bch.ResultVar(units="ms", doc="Sample cache initialization time")
    throughput = bch.ResultVar(units="samples/s", doc="Samples processed per second")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        workload = TrivialWorkload()
        x_sweep = bch.FloatSweep(
            default=0, bounds=[0, 1], samples=self.num_samples, doc="input"
        )
        x_sweep.name = "x"

        inner_cfg = bch.BenchRunCfg()
        inner_cfg.repeats = 1
        inner_cfg.cache_samples = self.use_cache
        inner_cfg.cache_results = False
        inner_cfg.auto_plot = False

        bench = bch.Bench("inner_bench", workload, run_cfg=inner_cfg)
        bench.plot_sweep(input_vars=[x_sweep], result_vars=["result"])
        res = bench.results[-1]

        t = res.timings
        self.total_ms = t.total_ms
        self.dataset_setup_ms = t.dataset_setup_ms
        self.job_submission_ms = t.job_submission_ms
        self.job_execution_ms = t.job_execution_ms
        self.cache_check_ms = t.cache_check_ms
        self.sample_cache_init_ms = t.sample_cache_init_ms
        self.throughput = (self.num_samples / t.total_ms * 1000) if t.total_ms > 0 else 0

        return super().__call__(**kwargs)'''

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
            filename="self_benchmark",
            function_name="example_self_benchmark",
            imports=imports,
            body=body,
            class_code=class_code,
        )


def example_meta_performance():
    """Generate all performance self-introspection examples."""
    gen = MetaPerformance()
    for example in PERFORMANCE_EXAMPLES:
        gen(example=example)
