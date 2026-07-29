"""Auto-generated example: Plot Type: Xy Histogram."""

import numpy as np
import pandas as pd

import bencher as bn
from bencher.results.holoview_results.xy_histogram_result import XYHistogramResult


class LatencySamples(bn.ParametrizedSweep):
    """Every request timed, not just the mean: the sample *is* the distribution."""

    concurrency = bn.IntSweep(default=4, bounds=[1, 16], doc="Concurrent requests")

    latencies = bn.ResultDataSet(doc="One row per request, measured and baseline")

    def benchmark(self):
        rng = np.random.default_rng(self.concurrency)
        scale = 1.0 + 0.4 * self.concurrency
        self.latencies = bn.ResultDataSet(
            pd.DataFrame(
                {
                    "latency_ms": rng.gamma(3.0, scale, 4000),
                    "baseline_ms": rng.gamma(3.0, 1.4, 4000),
                }
            )
        )


def example_plot_xy_histogram(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Xy Histogram."""
    bench = LatencySamples().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["concurrency"], result_vars=["latencies"])
    bench.report.append(
        res.to(
            XYHistogramResult, column=["latency_ms", "baseline_ms"], bins=40, xlabel="latency [ms]"
        )
    )

    return bench


if __name__ == "__main__":
    bn.run(example_plot_xy_histogram, subsampling_divisions=3)
