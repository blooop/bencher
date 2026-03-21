"""Auto-generated example: Result Vec: 2D input."""

from typing import Any

import math

import bencher as bn


class SystemMetrics(bn.ParametrizedSweep):
    """Returns a [cpu, mem, disk] utilization vector."""

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="System load factor")
    instances = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Number of instances")

    metrics = bn.ResultVec(3, "%", doc="CPU, memory, disk utilization")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        cpu = 20.0 + 70.0 * math.sin(math.pi * self.load / 2.0)
        mem = 30.0 + 50.0 * self.load * math.log1p(self.instances)
        disk = 10.0 + 40.0 * math.sqrt(self.load * self.instances / 10.0)
        self.metrics = [cpu, mem, disk]
        return super().__call__()


def example_result_vec_2d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Result Vec: 2D input."""
    bench = SystemMetrics().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["load", "instances"],
        result_vars=["metrics"],
        description="Demonstrates a fixed-size numeric vector with 2D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_result_vec_2d, level=2)
