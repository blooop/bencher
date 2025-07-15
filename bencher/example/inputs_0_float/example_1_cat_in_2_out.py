"""This file demonstrates benchmarking with 1 categorical input and 2 output variables.

It benchmarks different Python data structures to compare their performance characteristics
using simulated performance data to illustrate how benchmarking works.
"""

import random
import bencher as bch

random.seed(0)


class PythonOperations1CatBenchmark(bch.ParametrizedSweep):
    """Example class for benchmarking different Python data structures using 1 categorical variable.

    This class demonstrates how to structure a benchmark with a single input parameter
    and multiple output metrics. It uses simulated performance data that follows realistic
    patterns while being deterministic and reproducible.
    """

    data_structure = bch.StringSweep(["list", "dict"], doc="Type of data structure to operate on")

    # Using fixed read operation and medium size data

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

        # Use deterministic fake data based on parameters
        # Base values (for read operation on medium data)
        base_time = 35.0  # ms (medium size, read operation base)
        base_memory = 800.0  # KB (medium size, read operation base)

        # Adjust for data structure (lists are generally faster but use more memory)
        if self.data_structure == "list":
            time_factor = 0.8
            memory_factor = 1.2
        else:  # dict
            time_factor = 1.2
            memory_factor = 0.9

        # Calculate final metrics with significant variance to show differences
        self.execution_time = base_time * time_factor * random.gauss(0.80, 1.20)
        self.memory_peak = base_memory * memory_factor * random.gauss(0.85, 1.15)

        return super().__call__(**kwargs)


def example_1_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example demonstrates benchmarking with 1 categorical variable and multiple output metrics.

    It creates a synthetic benchmark that simulates performance characteristics of different
    Python data structures (list vs dict) using a fixed read operation and medium data size.
    The benchmark produces realistic patterns of execution time and memory usage without
    actually executing real operations, making it ideal for learning and demonstration.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 5  # Fewer repeats for a quicker benchmark
    bench = PythonOperations1CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Python Data Structure Performance Benchmark (1 Variable)",
        description="Comparing execution time and peak memory usage between lists and dictionaries",
        post_description="""
        This benchmark illustrates how different data structures affect performance.
        
        Key observations:
        - Lists generally process faster than dictionaries for read operations
        - However, lists consume more memory than dictionaries
        - All tests were performed with read operations on medium-sized datasets
        - Note that variance in the results simulates real-world measurement fluctuations
        """,
    )
    return bench


if __name__ == "__main__":
    example_1_cat_in_2_out().report.show()
