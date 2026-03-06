"""Auto-generated example: 3 Float, 0 Categorical."""

import bencher as bch
import math


class HashBenchmark(bch.ParametrizedSweep):
    """Hash throughput across key size, payload size, and iterations."""

    key_size = bch.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bch.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bch.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")

    throughput = bch.ResultVar(units="MB/s", doc="Hash throughput")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.throughput = (
            500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        self.throughput += __import__("random").gauss(0, 0.15 * 30)
        return super().__call__()


def example_with_repeats_3_float_0_cat(run_cfg=None):
    """3 Float, 0 Categorical."""
    bench = HashBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations"], result_vars=["throughput"]
    )

    return bench


if __name__ == "__main__":
    bch.run(example_with_repeats_3_float_0_cat, level=4, repeats=3)
