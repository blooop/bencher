"""Auto-generated example: Aggregate to 1-D (True)."""

from typing import Any

import random
import math

import bencher as bn


class SortComparison(bn.ParametrizedSweep):
    """Compares sort duration across array sizes and algorithms."""

    array_size = bn.FloatSweep(default=100, bounds=[10, 10000], doc="Array length")
    algorithm = bn.StringSweep(["quicksort", "mergesort", "heapsort"], doc="Sort algorithm")

    time = bn.ResultVar(units="ms", doc="Sort duration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        algo_factor = {"quicksort": 1.0, "mergesort": 1.2, "heapsort": 1.5}[self.algorithm]
        self.time = algo_factor * self.array_size * math.log2(self.array_size + 1) * 0.001
        self.time += random.gauss(0, 0.15 * self.time)
        return super().__call__()


def example_agg_all(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate to 1-D (True)."""
    bench = SortComparison().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["array_size", "algorithm"],
        result_vars=["time"],
        description="Setting aggregate=True collapses all but the first input dimension, reducing the sweep to a 1-D plot. Useful when you want a simple curve from a multi-dimensional sweep.",
        post_description="The aggregated view collapses all inputs except the first into a single mean ± std curve. The non-aggregated view below shows the full detail.",
        aggregate=True,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_all, level=4, repeats=3)
