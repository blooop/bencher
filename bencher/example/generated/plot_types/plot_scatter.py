"""Auto-generated example: Plot Type: Scatter."""

import bencher as bch


class ThroughputCompare(bch.ParametrizedSweep):
    """Throughput comparison across backends."""

    backend = bch.StringSweep(["redis", "memcached", "local"])

    distance = bch.ResultVar("m", doc="Throughput distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 5.4, "memcached": 4.1, "local": 8.7}
        self.distance = lookup[self.backend]
        return super().__call__()


def example_plot_scatter(run_cfg=None):
    """Plot Type: Scatter."""
    bench = ThroughputCompare().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["distance"])
    bench.report.append(res.to_scatter())

    return bench


if __name__ == "__main__":
    bch.run(example_plot_scatter, level=3)
