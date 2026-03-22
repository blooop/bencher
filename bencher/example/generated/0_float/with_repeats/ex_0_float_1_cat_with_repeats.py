"""Auto-generated example: 0 Float, 1 Categorical (with repeats)."""

from typing import Any

import random

import bencher as bn


class CacheBackend(bn.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bn.ResultVar(units="ms", doc="Cache lookup latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base + random.gauss(0, 0.15 * base)
        return super().__call__()


def example_0_float_1_cat_with_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 1 Categorical (with repeats)."""
    bench = CacheBackend().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["backend"], result_vars=["latency"])

    return bench


if __name__ == "__main__":
    bn.run(example_0_float_1_cat_with_repeats, level=4, repeats=10)
