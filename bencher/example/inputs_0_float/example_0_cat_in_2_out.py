"""This file demonstrates benchmarking with 0 categorical inputs and 2 output variables.

It benchmarks a single Python operation configuration to showcase output variations
using simulated performance data to illustrate how benchmarking works with fixed inputs.
"""

import random
import bencher as bch

random.seed(0)


class PythonOperations0CatBenchmark(bch.ParametrizedSweep):
    """Example class for benchmarking with no categorical variables.

    This class demonstrates how to structure a benchmark with fixed inputs
    and multiple output metrics. It uses simulated performance data that follows realistic
    patterns while being deterministic and reproducible.
    """

    # All inputs are fixed (list data structure, read operation, medium size)

    execution_time = bch.ResultVar(units="ms", doc="Execution time in milliseconds")
    memory_peak = bch.ResultVar(units="KB", doc="Peak memory usage in kilobytes")

    def __call__(self, **kwargs) -> dict:
        """Execute the benchmark for the given set of parameters.

        Args:
            **kwargs: Parameters to update before executing

        Returns:
            dict: Dictionary containing the benchmark results
        """
        self.update_params_from_kwargs(**kwargs)

        # Base values for list read operation on medium data
        base_time = 28.0  # ms
        base_memory = 960.0  # KB

        # Add significant variance to show distribution of results
        # even with fixed inputs
        self.execution_time = base_time * random.gauss(0.75, 1.25)
        self.memory_peak = base_memory * random.gauss(0.80, 1.20)

        return super().__call__(**kwargs)


def example_0_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example demonstrates benchmarking with no categorical variables and multiple output metrics.

    It creates a synthetic benchmark that simulates performance variations when repeatedly running
    the same operation (list read operation on medium data). This example shows that even with
    fixed inputs, repeated benchmark runs produce variations in performance metrics.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 100  # More repeats to show distribution
    bench = PythonOperations0CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Python List Read Operation Performance (Fixed Inputs)",
        description="Distribution of execution time and peak memory usage across multiple runs",
        post_description="""
        This benchmark illustrates how performance metrics vary even with fixed inputs.
        
        Key observations:
        - Each run uses the same configuration: list data structure, read operation, medium data size
        - Despite identical inputs, performance metrics show natural variations
        - This variance simulates real-world system fluctuations that occur in benchmarking
        - With no categorical variables, the benchmark helps establish baseline performance
          distribution for a single configuration
        """,
    )
    return bench


if __name__ == "__main__":
    example_0_cat_in_2_out().report.show()
