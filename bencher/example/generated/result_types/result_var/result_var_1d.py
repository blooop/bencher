"""Auto-generated example: Result Var: 1D input."""

from typing import Any

import math
import bencher as bch


class ResponseTimer(bch.ParametrizedSweep):
    """Measures HTTP request latency across endpoints and concurrency levels."""

    endpoint = bch.StringSweep(["api/users", "api/orders"], doc="API endpoint")
    concurrency = bch.FloatSweep(default=50, bounds=[1, 100], doc="Concurrent requests")

    latency = bch.ResultVar(units="ms", doc="Response latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"api/users": 12.0, "api/orders": 25.0}[self.endpoint]
        self.latency = base + 0.5 * math.log1p(self.concurrency)
        return super().__call__()


def example_result_var_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Var: 1D input."""
    bench = ResponseTimer().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["concurrency"],
        result_vars=["latency"],
        description="Demonstrates a scalar numeric metric with units with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_var_1d, level=3)
