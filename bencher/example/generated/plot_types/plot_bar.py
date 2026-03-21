"""Auto-generated example: Plot Type: Bar."""

from typing import Any

import bencher as bn


class CacheCompare(bn.ParametrizedSweep):
    """Compare response distance across cache backends."""

    backend = bn.StringSweep(["redis", "memcached", "local"])

    distance = bn.ResultVar("m", doc="Response distance metric")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        return super().__call__()


def example_plot_bar(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Bar."""
    bench = CacheCompare().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["backend"], result_vars=["distance"])
    bench.report.append(res.to_bar())

    return bench


if __name__ == "__main__":
    bn.run(example_plot_bar, level=3)
