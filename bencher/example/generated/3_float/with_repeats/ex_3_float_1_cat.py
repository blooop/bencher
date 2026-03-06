"""Auto-generated example: 3 Float, 1 Categorical."""

from typing import Any

import bencher as bch
import math


class HashComparison(bch.ParametrizedSweep):
    """Hash throughput across key size, payload, iterations, and algorithm."""

    key_size = bch.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bch.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bch.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")
    algorithm = bch.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")

    throughput = bch.ResultVar(units="MB/s", doc="Hash throughput")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_speed = {"sha256": 1.0, "blake2": 1.4, "md5": 1.8}[self.algorithm]
        self.throughput = (
            algo_speed
            * 500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        self.throughput += __import__("random").gauss(0, 0.15 * 30)
        return super().__call__()


def example_with_repeats_3_float_1_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """3 Float, 1 Categorical."""
    bench = HashComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations", "algorithm"],
        result_vars=["throughput"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_3_float_1_cat, level=4, repeats=3)
