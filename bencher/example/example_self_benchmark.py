"""Bencher self-introspection: benchmarks bencher's own overhead across problem sizes.

This example uses bencher to benchmark itself, sweeping over the number of parameter
samples and measuring the framework's timing for each phase of a sweep. The results
reveal how overhead scales with problem size, helping identify optimization targets.

Run locally:
    python bencher/example/example_self_benchmark.py
"""

import bencher as bch


class TrivialWorkload(bch.ParametrizedSweep):
    """A near-zero-cost worker so we measure framework overhead, not compute."""

    x = bch.FloatSweep(default=0, bounds=[0, 1], samples=2)
    result = bch.ResultVar(units="v", doc="trivial output")

    def __call__(self, **kwargs):
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

    # Result variables — one per timing phase
    total_ms = bch.ResultVar(units="ms", doc="Total sweep wall-clock time")
    dataset_setup_ms = bch.ResultVar(units="ms", doc="Dataset initialization time")
    job_submit_and_execute_ms = bch.ResultVar(
        units="ms", doc="Job creation, submission, and execution time"
    )
    result_collection_ms = bch.ResultVar(units="ms", doc="Result collection and storage time")
    cache_check_ms = bch.ResultVar(units="ms", doc="Benchmark cache lookup time")
    sample_cache_init_ms = bch.ResultVar(units="ms", doc="Sample cache initialization time")
    throughput = bch.ResultVar(units="samples/s", doc="Samples processed per second")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        workload = TrivialWorkload()
        x_sweep = bch.FloatSweep(default=0, bounds=[0, 1], samples=self.num_samples, doc="input")
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
        self.job_submit_and_execute_ms = t.job_submit_and_execute_ms
        self.result_collection_ms = t.result_collection_ms
        self.cache_check_ms = t.cache_check_ms
        self.sample_cache_init_ms = t.sample_cache_init_ms
        self.throughput = (self.num_samples / t.total_ms * 1000) if t.total_ms > 0 else 0

        return super().__call__(**kwargs)


def example_self_benchmark(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Benchmark bencher's own overhead across problem sizes."""
    bench = BencherSelfBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["num_samples"],
        result_vars=[
            "total_ms",
            "dataset_setup_ms",
            "job_submit_and_execute_ms",
            "result_collection_ms",
        ],
        title="Bencher Self-Benchmark: Phase Timing vs Problem Size",
    )
    bench.plot_sweep(
        input_vars=["num_samples"],
        result_vars=["throughput"],
        title="Bencher Self-Benchmark: Throughput vs Problem Size",
    )
    bench.plot_sweep(
        input_vars=["num_samples", "use_cache"],
        result_vars=["total_ms"],
        title="Bencher Self-Benchmark: Cache Impact",
    )
    return bench


if __name__ == "__main__":
    bch.run(example_self_benchmark)
