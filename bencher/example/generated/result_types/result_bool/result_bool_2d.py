"""Auto-generated example: Result Bool: 2D input."""

import bencher as bch
import math


class HealthChecker(bch.ParametrizedSweep):
    """Checks whether a service passes its health threshold."""

    threshold = bch.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")
    difficulty = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)
        self.healthy = score > 0.5
        return super().__call__()


def example_result_bool_2d(run_cfg=None):
    """Result Bool: 2D input."""
    bench = HealthChecker().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["threshold", "difficulty"],
        result_vars=["healthy"],
        description="Demonstrates a boolean pass/fail outcome with 2D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_bool_2d, level=2)
