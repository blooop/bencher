"""Auto-generated example: 3 Float, 0 Categorical (with repeats)."""

from typing import Any

import random
import math

import bencher as bn


class HashBenchmark(bn.ParametrizedSweep):
    """Hash throughput across key size, payload size, and iterations."""

    key_size = bn.FloatSweep(default=32, bounds=[8, 256], doc="Key size in bytes")
    payload_size = bn.FloatSweep(default=1024, bounds=[64, 65536], doc="Payload size in bytes")
    iterations = bn.FloatSweep(default=100, bounds=[10, 1000], doc="Hash iterations")

    throughput = bn.ResultVar(units="MB/s", doc="Hash throughput")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.throughput = (
            500.0
            / (1.0 + 0.5 * math.log2(self.key_size / 8))
            / (1.0 + 0.3 * math.log2(self.payload_size / 64))
            * (self.iterations / 100)
        )
        self.throughput += random.gauss(0, 0.15 * 30)
        return super().__call__()


def example_sweep_3_float_0_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """3 Float, 0 Categorical (with repeats)."""
    bench = HashBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["key_size", "payload_size", "iterations"],
        result_vars=["throughput"],
        description=(
            "A 3 float + 0 categorical parameter sweep with multiple repeats per combination. "
            "Repeating measurements reveals the noise structure of your benchmark. If your "
            "function is deterministic, all repeats will be identical; if it has stochastic "
            "components, repeats let you estimate confidence intervals and distinguish signal "
            "from noise. The benchmark function must be pure -- if past calls affect future "
            "calls through side effects, the statistics will be invalid. A 3D float sweep "
            "produces a volumetric representation. This is useful for visualising scalar "
            "fields in 3D parameter spaces."
        ),
        post_description=(
            "Swarm/violin plots show the distribution of repeated measurements. If repeat has "
            "high variance, it suggests either measurement noise or unintended side effects "
            "in the benchmark function."
        ),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_3_float_0_cat_with_repeats, level=4, repeats=3)
