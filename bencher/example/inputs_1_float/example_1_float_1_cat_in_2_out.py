"""This file demonstrates benchmarking with 1 float and 1 categorical input with 2 output variables.

It benchmarks different algorithmic implementations to compare their performance characteristics
using simulated performance data to illustrate how benchmarking works.
"""

import random
import math
import bencher as bch

random.seed(0)


class Algorithm1CatBenchmark(bch.ParametrizedSweep):
    """Example class for benchmarking algorithm performance with fewer parameters.

    This class demonstrates how to structure a benchmark with one float parameter and
    one categorical parameter, producing multiple output metrics. It uses simulated
    performance data that follows realistic patterns while being deterministic.
    """

    # Float input parameter
    problem_size = bch.FloatSweep(default=100, bounds=[1, 100], doc="Size of the problem to solve")

    # Categorical input parameter
    algorithm_type = bch.StringSweep(
        ["recursive", "iterative"], doc="Type of algorithm implementation"
    )

    # Using fixed "array" data structure and "basic" optimization level

    # Output metrics
    execution_time = bch.ResultVar(units="ms", doc="Execution time in milliseconds")
    memory_usage = bch.ResultVar(units="MB", doc="Memory usage in megabytes")

    def __call__(self, **kwargs) -> dict:
        """Execute the benchmark for the given set of parameters.

        Args:
            **kwargs: Parameters to update before executing

        Returns:
            dict: Dictionary containing the benchmark results
        """
        self.update_params_from_kwargs(**kwargs)

        # Base values for calculation
        base_time = 1.0  # ms
        base_memory = 0.1  # MB

        # Size factor (non-linear relationship with problem size)
        size_factor_time = math.log10(self.problem_size) ** 1.5
        size_factor_memory = math.sqrt(self.problem_size) / 10

        # Algorithm type factor
        if self.algorithm_type == "recursive":
            algo_time_factor = 1.2  # Recursive is slower
            algo_memory_factor = 1.5  # Recursive uses more memory (stack)
        else:  # iterative
            algo_time_factor = 0.8  # Iterative is faster
            algo_memory_factor = 0.7  # Iterative uses less memory

        # Fixed "array" data structure factors (from previous example)
        ds_time_factor = 0.9  # Arrays have faster access
        ds_memory_factor = 1.1  # Arrays use slightly more contiguous memory

        # Fixed "basic" optimization level factors (from previous example)
        opt_time_factor = 1.0
        opt_memory_factor = 1.0

        # Calculate final metrics with some random variation
        time_multiplier = (
            algo_time_factor * ds_time_factor * opt_time_factor * random.uniform(0.9, 1.1)
        )
        memory_multiplier = (
            algo_memory_factor * ds_memory_factor * opt_memory_factor * random.uniform(0.95, 1.05)
        )

        self.execution_time = base_time * size_factor_time * time_multiplier
        self.memory_usage = base_memory * size_factor_memory * memory_multiplier

        return super().__call__(**kwargs)


def example_1_float_1_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example demonstrates benchmarking with 1 float and 1 categorical input.

    It creates a synthetic benchmark that simulates performance characteristics of different
    algorithm implementations, varying problem size (float) and algorithm type. The benchmark
    uses fixed "array" data structure and "basic" optimization level, producing realistic
    patterns of execution time and memory usage without actually executing real algorithms.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 3  # Fewer repeats for a quicker benchmark
    bench = Algorithm1CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Algorithm Performance Benchmark (1 Float, 1 Categorical Variable)",
        description="Comparing execution time and memory usage across problem sizes and algorithm types",
        post_description="""
        This benchmark illustrates how different algorithm implementations affect performance across problem sizes.
        
        Key observations:
        - Execution time increases non-linearly with problem size
        - Iterative algorithms typically outperform recursive ones in both time and memory usage
        - All tests were performed with array data structure and basic optimization level
        - The performance gap between recursive and iterative approaches widens as problem size increases
        """,
    )
    return bench


if __name__ == "__main__":
    example_1_float_1_cat_in_2_out().report.show()
