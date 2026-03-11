"""Auto-generated example: Bool Plot: Histogram."""

from typing import Any

import random

import bencher as bch
from bencher.results.histogram_result import HistogramResult


class CoinFlip(bch.ParametrizedSweep):
    """Simple coin flip with no inputs — shows distribution of True/False."""

    heads = bch.ResultBool(doc="Whether the coin landed heads")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.heads = random.random() < 0.5
        return super().__call__()


def example_bool_plot_histogram(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Bool Plot: Histogram."""
    bench = CoinFlip().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=[], result_vars=["heads"])
    bench.report.append(res.to(HistogramResult))

    return bench


if __name__ == "__main__":
    bch.run(example_bool_plot_histogram, level=3, repeats=20)
