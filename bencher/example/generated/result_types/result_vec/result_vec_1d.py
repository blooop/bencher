"""Auto-generated example: Result Vec: 1D input."""

from typing import Any

import math
import bencher as bch

import bencher as bch


class SystemMetrics(bch.ParametrizedSweep):
    """Returns a [cpu, mem, disk] utilization vector."""

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="System load factor")
    instances = bch.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Number of instances")

    metrics = bch.ResultVec(3, "%", doc="CPU, memory, disk utilization")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        cpu = 20.0 + 70.0 * math.sin(math.pi * self.load / 2.0)
        mem = 30.0 + 50.0 * self.load * math.log1p(self.instances)
        disk = 10.0 + 40.0 * math.sqrt(self.load * self.instances / 10.0)
        self.metrics = [cpu, mem, disk]
        return super().__call__()


def example_result_vec_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Vec: 1D input."""
    bench = SystemMetrics().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["load"],
        result_vars=["metrics"],
        description="Demonstrates a fixed-size numeric vector with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_vec_1d, level=3)
