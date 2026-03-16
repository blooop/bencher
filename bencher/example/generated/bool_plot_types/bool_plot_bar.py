"""Auto-generated example: Bool Plot: Bar."""

from typing import Any

import random

import bencher as bch


class HealthCheckCat(bch.ParametrizedSweep):
    """Check service health across backends with varying reliability."""

    backend = bch.StringSweep(["postgres", "redis", "memcached", "sqlite", "local"])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        rates = {"postgres": 0.95, "redis": 0.85, "memcached": 0.65, "sqlite": 0.40, "local": 0.15}
        self.healthy = random.random() < rates[self.backend]
        return super().__call__()


def example_bool_plot_bar(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Bar."""
    bench = HealthCheckCat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["healthy"])
    bench.report.append(res.to_bar())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_bar, level=3, repeats=30)
