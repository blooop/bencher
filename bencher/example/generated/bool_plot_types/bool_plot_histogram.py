"""Auto-generated example: Bool Plot: Histogram."""

import random

from bencher.results.histogram_result import HistogramResult
import bencher as bn


class PassRateFloat(bn.ParametrizedSweep):
    """Test pass rate that decreases with complexity."""

    complexity = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    passed = bn.ResultBool(doc="Whether the test passed")

    def benchmark(self):
        rate = 1.0 - 0.8 * self.complexity**1.5
        self.passed = random.random() < rate


def example_bool_plot_histogram(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Bool Plot: Histogram."""
    bench = PassRateFloat().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["complexity"], result_vars=["passed"])
    bench.report.append(res.to(HistogramResult))

    return bench


if __name__ == "__main__":
    bn.run(example_bool_plot_histogram, level=3, repeats=30)
