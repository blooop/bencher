"""Auto-generated example: 0 Float, 1 Categorical (with repeats)."""

import random

import bencher as bn


class CacheBackend(bn.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bn.ResultFloat(units="ms", doc="Cache lookup latency")

    def benchmark(self):
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base + random.gauss(0, 0.15 * base)


def example_sweep_0_float_1_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 1 Categorical (with repeats)."""
    bench = CacheBackend().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["backend"],
        result_vars=["latency"],
        description="A 0 float + 1 categorical parameter sweep with multiple repeats per combination. Repeating measurements reveals the noise structure of your benchmark. If your function is deterministic, all repeats will be identical; if it has stochastic components, repeats let you estimate confidence intervals and distinguish signal from noise. The benchmark function must be pure -- if past calls affect future calls through side effects, the statistics will be invalid. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
        post_description="Swarm/violin plots show the distribution of repeated measurements. If repeat has high variance, it suggests either measurement noise or unintended side effects in the benchmark function.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_1_cat_with_repeats, level=4, repeats=10)
