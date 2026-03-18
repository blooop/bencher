"""Auto-generated example: Bool Plot: Violin."""

from typing import Any

import random

from bencher.results.holoview_results.distribution_result.violin_result import ViolinResult
import bencher as bch


class ReliabilityCat(bch.ParametrizedSweep):
    """Service reliability check with varying pass rates across backends."""

    backend = bch.StringSweep(["postgres", "redis", "memcached", "sqlite", "local"])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        rates = {"postgres": 0.95, "redis": 0.85, "memcached": 0.65, "sqlite": 0.40, "local": 0.15}
        self.healthy = random.random() < rates[self.backend]
        return super().__call__()


def example_bool_plot_violin(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Violin."""
    bench = ReliabilityCat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["healthy"])
    bench.report.append(res.to(ViolinResult))

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_violin, level=3, repeats=50)
