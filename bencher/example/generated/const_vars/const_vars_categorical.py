"""Auto-generated example: Const Vars: Fixing Categorical Parameters."""

from typing import Any

import bencher as bch


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

    def __call__(self, **kwargs: Any) -> Any:
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
        return super().__call__()


def example_const_vars_categorical(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Const Vars: Fixing Categorical Parameters."""
    bench = ServerBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        title="Sweep cpu_load x backend, with cache_enabled=True",
        input_vars=["cpu_load", "backend"],
        result_vars=["latency"],
        const_vars=dict(cache_enabled=True),
    )
    bench.plot_sweep(
        title="Sweep cpu_load x backend, with cache_enabled=False",
        input_vars=["cpu_load", "backend"],
        result_vars=["latency"],
        const_vars=dict(cache_enabled=False),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_const_vars_categorical, level=4)
