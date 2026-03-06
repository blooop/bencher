"""Meta-generator: Constant Variables.

Shows how to use const_vars to fix parameters at specific values while sweeping others.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "const_vars"

EXAMPLES = ["slice", "compare", "categorical", "noise"]

SERVER_BENCHMARK_CLASS_CODE = '''\
class ServerBenchmark(bch.ParametrizedSweep):
    """Simulates server performance metrics under varying load conditions."""

    cpu_load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="CPU load factor")
    memory_pct = bch.FloatSweep(default=50, bounds=[10, 90], doc="Memory usage percentage")
    disk_io = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Disk I/O pressure")
    cache_enabled = bch.BoolSweep(default=True, doc="Whether caching is enabled")
    backend = bch.StringSweep(["postgres", "mysql", "sqlite"], doc="Database backend")
    log_level = bch.StringSweep(["debug", "info", "warn"], doc="Logging verbosity")
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    latency = bch.ResultVar(units="ms", doc="Request latency")
    throughput = bch.ResultVar(units="req/s", doc="Request throughput")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        cache_factor = 0.6 if self.cache_enabled else 1.0
        db_base = {"postgres": 1.0, "mysql": 1.1, "sqlite": 0.7}[self.backend]
        log_penalty = {"debug": 1.3, "info": 1.0, "warn": 1.0}[self.log_level]
        self.latency = (
            db_base
            * cache_factor
            * log_penalty
            * (10 + 90 * self.cpu_load + 0.5 * self.memory_pct + 30 * self.disk_io)
        )
        self.throughput = 1000 / max(self.latency, 1)
        if self.noise_scale > 0:
            import random

            self.latency += random.gauss(0, self.noise_scale * self.latency * 0.1)
            self.throughput = 1000 / max(self.latency, 1)
        return super().__call__()'''


class MetaConstVars(MetaGeneratorBase):
    """Generate Python examples demonstrating const_vars usage."""

    example = bch.StringSweep(EXAMPLES, doc="Which const_vars example to generate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example == "slice":
            self._gen_slice()
        elif self.example == "compare":
            self._gen_compare()
        elif self.example == "categorical":
            self._gen_categorical()
        elif self.example == "noise":
            self._gen_noise()

        return super().__call__()

    def _gen_slice(self):
        """Fix disk_io=0.5 while sweeping cpu_load and memory_pct."""
        self.generate_sweep_example(
            title="Const Vars: Slicing a 3D Space",
            output_dir=OUTPUT_DIR,
            filename="const_vars_slice",
            function_name="example_const_vars_slice",
            benchable_class="ServerBenchmark",
            benchable_module=None,
            class_code=SERVER_BENCHMARK_CLASS_CODE,
            input_vars='["cpu_load", "memory_pct"]',
            result_vars='["latency"]',
            const_vars="dict(disk_io=0.5)",
            run_kwargs={"level": 3},
        )

    def _gen_compare(self):
        """Compare the same sweep at different fixed values of memory_pct."""
        imports = "import bencher as bch"
        body = (
            "bench = ServerBenchmark().to_bench(run_cfg)\n"
            "for mem_val in [20, 50, 80]:\n"
            "    bench.plot_sweep(\n"
            '        title=f"cpu_load sweep with memory_pct={mem_val}",\n'
            '        input_vars=["cpu_load"],\n'
            '        result_vars=["latency"],\n'
            "        const_vars=dict(memory_pct=mem_val, disk_io=0.5),\n"
            "    )\n"
        )
        self.generate_example(
            title="Const Vars: Comparing Slices",
            output_dir=OUTPUT_DIR,
            filename="const_vars_compare",
            function_name="example_const_vars_compare",
            imports=imports,
            body=body,
            class_code=SERVER_BENCHMARK_CLASS_CODE,
            run_kwargs={"level": 4},
        )

    def _gen_categorical(self):
        """Fix cache_enabled while sweeping cpu_load and backend."""
        imports = "import bencher as bch"
        body = (
            "bench = ServerBenchmark().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Sweep cpu_load x backend, with cache_enabled=True",\n'
            '    input_vars=["cpu_load", "backend"],\n'
            '    result_vars=["latency"],\n'
            "    const_vars=dict(cache_enabled=True),\n"
            ")\n"
            "bench.plot_sweep(\n"
            '    title="Sweep cpu_load x backend, with cache_enabled=False",\n'
            '    input_vars=["cpu_load", "backend"],\n'
            '    result_vars=["latency"],\n'
            "    const_vars=dict(cache_enabled=False),\n"
            ")\n"
        )
        self.generate_example(
            title="Const Vars: Fixing Categorical Parameters",
            output_dir=OUTPUT_DIR,
            filename="const_vars_categorical",
            function_name="example_const_vars_categorical",
            imports=imports,
            body=body,
            class_code=SERVER_BENCHMARK_CLASS_CODE,
            run_kwargs={"level": 4},
        )

    def _gen_noise(self):
        """Sweep cpu_load and memory_pct with noise enabled."""
        self.generate_sweep_example(
            title="Const Vars: Setting Non-Default Configuration",
            output_dir=OUTPUT_DIR,
            filename="const_vars_noise",
            function_name="example_const_vars_noise",
            benchable_class="ServerBenchmark",
            benchable_module=None,
            class_code=SERVER_BENCHMARK_CLASS_CODE,
            input_vars='["cpu_load", "memory_pct"]',
            result_vars='["latency", "throughput"]',
            const_vars="dict(noise_scale=0.3)",
            run_kwargs={"level": 3},
        )


def example_meta_const_vars(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaConstVars().to_bench(run_cfg)

    bench.plot_sweep(
        title="Constant Variables",
        input_vars=[bch.p("example", EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_const_vars)
