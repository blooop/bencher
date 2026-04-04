"""Auto-generated example: Result Bool: 0D input."""

import math

import bencher as bn


class HealthChecker(bn.ParametrizedSweep):
    """Checks whether a service passes its health threshold."""

    threshold = bn.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Decision threshold")
    difficulty = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Problem difficulty")

    healthy = bn.ResultBool(doc="Whether the service is healthy")

    def benchmark(self):
        score = math.sin(math.pi * self.threshold) * (1.0 - 0.5 * self.difficulty)
        self.healthy = score > 0.5


def example_result_bool_0d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Result Bool: 0D input."""
    bench = HealthChecker().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["difficulty"],
        result_vars=["healthy"],
        description="Demonstrates a boolean pass/fail outcome with 0D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_result_bool_0d, level=3)
