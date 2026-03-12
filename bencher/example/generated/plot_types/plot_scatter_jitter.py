"""Auto-generated example: Plot Type: Scatter Jitter."""

from typing import Any

from bencher.results.holoview_results.distribution_result.scatter_jitter_result import (
    ScatterJitterResult,
)
import bencher as bch

import random


class ScatterJitterDemo(bch.ParametrizedSweep):
    """Scatter with jitter across cache backends."""

    backend = bch.StringSweep(["redis", "memcached", "local"])
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Jittered distance metric")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)
        return super().__call__()


def example_plot_scatter_jitter(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Scatter Jitter."""
    bench = ScatterJitterDemo().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["backend"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to(ScatterJitterResult))

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter_jitter, level=3, repeats=10)
