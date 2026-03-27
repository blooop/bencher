"""Auto-generated example: 0 Float, 1 Categorical (no repeats)."""

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


def example_sweep_0_float_1_cat_no_repeats(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 1 Categorical (no repeats)."""
    bench = CacheBackend().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["backend"],
        result_vars=["latency"],
        description="A 0 float + 1 categorical parameter sweep with a single sample per combination. Bencher calculates the Cartesian product of all input variables and evaluates the benchmark function at each point. With no repeats, each combination appears exactly once -- useful for deterministic functions or quick exploration before committing to longer runs. Categorical-only sweeps produce bar/swarm plots comparing discrete settings.",
        post_description="Each tab shows a different view of the same data: interactive plots, tabular summaries, and raw data. Use the tabs to explore the sweep results from different angles.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_sweep_0_float_1_cat_no_repeats, level=4)
