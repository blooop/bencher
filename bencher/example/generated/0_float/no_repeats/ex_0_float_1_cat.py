"""Auto-generated example: 0 Float, 1 Categorical."""

from typing import Any

import bencher as bn


class CacheBackend(bn.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bn.ResultVar(units="ms", doc="Cache lookup latency")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base
        return super().__call__()


def example_no_repeats_0_float_1_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 1 Categorical."""
    bench = CacheBackend().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["backend"], result_vars=["latency"])

    return bench


if __name__ == "__main__":
    bn.run(example_no_repeats_0_float_1_cat, level=4)
