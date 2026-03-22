"""Auto-generated example: 3 Float, 1 Categorical (with repeats)."""

from typing import Any

import random
import math

import bencher as bn


class HashComparison(bn.ParametrizedSweep):
    """Hash throughput across key size, payload, iterations, and algorithm."""

    key_size = bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")
    algorithm = bn.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")

    throughput = bn.ResultVar(units="MB/s", doc="Hash throughput")

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
        self.throughput += random.gauss(0, 0.15 * 30)
        return super().__call__()


def example_3_float_1_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """3 Float, 1 Categorical (with repeats)."""
    bench = HashComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations", "algorithm"],
        result_vars=["throughput"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_3_float_1_cat_with_repeats, level=4, repeats=3)
