"""Auto-generated example: 0 Float, 1 Categorical."""

import bencher as bch


class CacheBackend(bch.ParametrizedSweep):
    """Compares latency across different cache backends."""

    backend = bch.StringSweep(["redis", "memcached", "local"], doc="Cache backend")

    latency = bch.ResultVar(units="ms", doc="Cache lookup latency")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        base = {"redis": 1.2, "memcached": 1.5, "local": 0.3}[self.backend]
        self.latency = base
        return super().__call__()


def example_no_repeats_0_float_1_cat(run_cfg=None):
    """0 Float, 1 Categorical."""
    bench = CacheBackend().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["backend"], result_vars=["latency"])

    return bench


if __name__ == "__main__":
    bch.run(example_no_repeats_0_float_1_cat, level=4)
