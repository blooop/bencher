"""Auto-generated example: Plot Type: Line."""

from typing import Any

import bencher as bn

import math


class LatencyProfile(bn.ParametrizedSweep):
    """Latency as a function of load."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultVar("m", doc="Latency distance metric")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.load) + 0.5
        return super().__call__()


def example_plot_line(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Line."""
    bench = LatencyProfile().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["load"], result_vars=["distance"])
    bench.report.append(res.to_line())

    return bench


if __name__ == "__main__":
    bn.run(example_plot_line, level=3)
