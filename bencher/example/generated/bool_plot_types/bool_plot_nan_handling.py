"""Auto-generated example: Bool Plot: Nan Handling."""

from typing import Any

import bencher as bch

import random


class FlakyService(bch.ParametrizedSweep):
    """Service that sometimes fails entirely (returns NaN).

    Demonstrates that ResultBool handles missing data gracefully.
    NaN values are skipped during aggregation so the bar chart
    shows the success rate computed from valid runs only.
    """

    backend = bch.StringSweep(["redis", "memcached", "local"])

    healthy = bch.ResultBool(doc="Whether the service responded")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        failure_rates = {"redis": 0.1, "memcached": 0.3, "local": 0.0}
        if random.random() < failure_rates[self.backend]:
            self.healthy = float("nan")  # service did not respond
        else:
            self.healthy = random.random() < 0.8
        return super().__call__()


def example_bool_plot_nan_handling(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Nan Handling."""
    bench = FlakyService().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["healthy"])
    bench.report.append(res.to_bar())

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_nan_handling, level=3, repeats=10)
