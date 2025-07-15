"""This file demonstrates benchmarking with 3 categorical inputs and 2 output variables.

It benchmarks different Python operations to compare their performance characteristics
using simulated performance data to illustrate how benchmarking works.
"""

import random
import bencher as bch

random.seed(0)


class PythonOperationsBenchmark(bch.ParametrizedSweep):
    """Example class for benchmarking different Python operations using categorical variables.

    This class demonstrates how to structure a benchmark with multiple input parameters
    and multiple output metrics. It uses simulated performance data that follows realistic
    patterns while being deterministic and reproducible.
    """

    data_structure = bch.StringSweep(["list", "dict"], doc="Type of data structure to operate on")
    operation_type = bch.StringSweep(["read", "write"], doc="Type of operation to perform")
    data_size = bch.StringSweep(["small", "medium"], doc="Size of data to process")

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
        # Base values that will be modified by our parameters
        base_time = 10.0  # ms
        base_memory = 100.0  # KB

        # Adjust for data structure (lists are generally faster but use more memory)
        if self.data_structure == "list":
            time_factor = 0.8
            memory_factor = 1.2
        else:  # dict
            time_factor = 1.2
            memory_factor = 0.9

        # Adjust for operation type (reads are faster than writes)
        if self.operation_type == "read":
            time_factor *= 0.7
            memory_factor *= 0.8
        else:  # write
            time_factor *= 1.4
            memory_factor *= 1.3

        # Adjust for data size
        if self.data_size == "medium":
            time_factor *= 5
            memory_factor *= 10

        # Calculate final metrics with increased variance
        self.execution_time = base_time * time_factor * random.gauss(0.85, 1.15)
        self.memory_peak = base_memory * memory_factor * random.gauss(0.90, 1.10)

        return super().__call__(**kwargs)


def example_3_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example demonstrates benchmarking with categorical variables and multiple output metrics.

    It creates a synthetic benchmark that simulates performance characteristics of different
    Python operations, varying data structures, operation types, and data sizes. The benchmark
    produces realistic patterns of execution time and memory usage without actually executing
    real operations, making it ideal for learning and demonstration.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 5  # Fewer repeats for a quicker benchmark
    bench = PythonOperationsBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Python Operations Performance Benchmark",
        description="Comparing execution time and peak memory usage across Python data structures and operations",
        post_description="""
        This benchmark illustrates how different data structures and operations affect performance.
        
        Key observations:
        - Lists generally process faster than dictionaries for these operations
        - Read operations outperform write operations as expected
        - Medium-sized data requires significantly more resources than small data
        - Note that variance in the results simulates real-world measurement fluctuations
        """,
    )
    return bench


if __name__ == "__main__":
    example_3_cat_in_2_out().report.show()
