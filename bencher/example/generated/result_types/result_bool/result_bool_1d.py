"""Auto-generated example: Result Bool: 1D input."""

from typing import Any

import math
import bencher as bch

import bencher as bch


class HealthChecker(bch.ParametrizedSweep):
    """Checks whether a service passes its health threshold."""

    threshold = bch.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")
    difficulty = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)
        self.healthy = score > 0.5
        return super().__call__()


def example_result_bool_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Bool: 1D input."""
    bench = HealthChecker().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["threshold"],
        result_vars=["healthy"],
        description="Demonstrates a boolean pass/fail outcome with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_1d, level=3)
