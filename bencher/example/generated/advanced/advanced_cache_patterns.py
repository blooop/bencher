"""Auto-generated example: Cache Patterns — run_tag and cache_samples."""

import math
import random
import bencher as bn


class NoisySensor(bn.ParametrizedSweep):
    """Simulates a sensor with configurable noise.

    Demonstrates cache_samples and run_tag usage. When cache_samples is True,
    each individual function call is cached so expensive computations are not
    repeated if the run is interrupted.
    """

    temperature = bn.FloatSweep(
        default=25.0, bounds=[0.0, 100.0], doc="Sensor temperature", units="C"
    )

    reading = bn.ResultVar(units="V", doc="Sensor voltage reading")

    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0], doc="Noise scale")

    def benchmark(self):
        self.reading = 0.5 + 0.03 * self.temperature + math.sin(self.temperature * 0.1)
        if self.noise_scale > 0:
            self.reading += random.gauss(0, self.noise_scale)


def example_advanced_cache_patterns(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Cache Patterns — run_tag and cache_samples."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=5)

    # run_tag partitions the cache so different experiment runs don't collide.
    run_cfg.run_tag = "sensor_v1"

    # cache_samples=True stores each individual call, useful for long-running
    # benchmarks that might be interrupted.
    run_cfg.cache_samples = True
    run_cfg.clear_sample_cache = True

    bench = NoisySensor().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["temperature"],
        result_vars=["reading"],
        const_vars=dict(noise_scale=0.3),
        description="Demonstrates cache_samples and run_tag for reliable benchmarking. "
        "cache_samples=True stores every function call individually so data is not "
        "lost if the run crashes. run_tag partitions the cache between experiments.",
        post_description="The repeated measurements show noise around the true sensor "
        "curve. If this run were interrupted, re-running would reuse cached samples.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_cache_patterns, level=3, repeats=5)
