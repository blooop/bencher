"""Auto-generated example: Plot Type: Box Whisker."""

from typing import Any

import bencher as bch
from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult

import random


class JitterDemo(bch.ParametrizedSweep):
    """Jitter distribution across cache backends."""

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


def example_plot_box_whisker(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Plot Type: Box Whisker."""
    bench = JitterDemo().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["backend"], result_vars=["distance"], const_vars=dict(noise_scale=0.15)
    )
    bench.report.append(res.to(BoxWhiskerResult))

    return bench


if __name__ == "__main__":
    bch.run(example_plot_box_whisker, level=3, repeats=10)
