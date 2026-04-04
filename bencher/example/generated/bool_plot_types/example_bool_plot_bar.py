"""Auto-generated example: Bool Plot: Bar."""

import random

import bencher as bn


class HealthCheckCat(bn.ParametrizedSweep):
    """Check service health across backends with varying reliability."""

    backend = bn.StringSweep(["postgres", "redis", "memcached", "sqlite", "local"])

    healthy = bn.ResultBool(doc="Whether the service is healthy")

    def benchmark(self):
        rates = {"postgres": 0.95, "redis": 0.85, "memcached": 0.65, "sqlite": 0.40, "local": 0.15}
        self.healthy = random.random() < rates[self.backend]


def example_bool_plot_bar(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Bool Plot: Bar."""
    bench = HealthCheckCat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["healthy"])
    bench.report.append(res.to_bar())

    return bench


if __name__ == "__main__":
    bn.run(example_bool_plot_bar, level=3, repeats=30)
