"""Auto-generated example: 3 Float, 1 Categorical (no repeats)."""

import math

import bencher as bn


class HashComparison(bn.ParametrizedSweep):
    """Hash throughput across key size, payload, iterations, and algorithm."""

    key_size = bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")
    algorithm = bn.StringSweep(["sha256", "blake2", "md5"], doc="Hash algorithm")

    throughput = bn.ResultVar(units="MB/s", doc="Hash throughput")

    def benchmark(self):
        algo_speed = {"sha256": 1.0, "blake2": 1.4, "md5": 1.8}[self.algorithm]
        self.throughput = (
            algo_speed
            * 500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )


def example_sweep_3_float_1_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """3 Float, 1 Categorical (no repeats)."""
    bench = HashComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations", "algorithm"],
        result_vars=["throughput"],
        description="A 3 float + 1 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. A 3D float sweep produces a volumetric representation. This is useful for visualising scalar fields in 3D parameter spaces.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_3_float_1_cat_no_repeats, level=4)
