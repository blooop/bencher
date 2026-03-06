"""Auto-generated example: 3 Float, 2 Categorical."""

import bencher as bch
import math


class HashAnalysis(bch.ParametrizedSweep):
    """Hash analysis: key size, payload, iterations, algorithm, and mode."""

    key_size = bch.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bch.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bch.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")
    algorithm = bch.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")
    mode = bch.StringSweep(["stream", "block"], doc="Processing mode")

    throughput = bch.ResultVar(units="MB/s", doc="Hash throughput")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        algo_speed = {"sha256": 1.0, "blake2": 1.4, "md5": 1.8}[self.algorithm]
        mode_factor = {"stream": 1.0, "block": 0.85}[self.mode]
        self.throughput = (
            algo_speed
            * mode_factor
            * 500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        return super().__call__()


def example_no_repeats_3_float_2_cat(run_cfg=None):
    """3 Float, 2 Categorical."""
    bench = HashAnalysis().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations", "algorithm", "mode"],
        result_vars=["throughput"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_3_float_2_cat, level=4)
