"""This file demonstrates benchmarking with 1 float input and 0 categorical inputs with 2 output variables.

It benchmarks a single algorithm configuration across different problem sizes to show
how performance scales, using simulated performance data to illustrate benchmarking basics.
"""

import random
import math
import bencher as bch

random.seed(0)


class Algorithm0CatBenchmark(bch.ParametrizedSweep):
    """Example class for benchmarking algorithm performance with just problem size.

    This class demonstrates how to structure a benchmark with one float parameter and
    no categorical parameters, producing multiple output metrics. It uses simulated
    performance data that follows realistic patterns while being deterministic.
    """

    # Float input parameter
    problem_size = bch.FloatSweep(default=100, bounds=[1, 100], doc="Size of the problem to solve")

    # Using fixed "iterative" algorithm, "array" data structure, and "basic" optimization level

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

        # Fixed "iterative" algorithm factors (from previous example)
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


def example_1_float_0_cat_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example demonstrates benchmarking with 1 float input and 0 categorical inputs.

    It creates a synthetic benchmark that simulates performance characteristics of an
    algorithm configuration across different problem sizes. The benchmark uses fixed
    "iterative" algorithm, "array" data structure, and "basic" optimization level,
    producing realistic patterns of execution time and memory usage without actually
    executing real algorithms.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 5  # Slightly more repeats to show variance
    bench = Algorithm0CatBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Algorithm Performance Benchmark (1 Float, 0 Categorical Variables)",
        description="Analyzing how execution time and memory usage scale with problem size",
        post_description="""
        This benchmark illustrates how algorithm performance scales with problem size.
        
        Key observations:
        - Execution time increases non-linearly with problem size (logarithmic relationship)
        - Memory usage scales more gradually (square root relationship)
        - All tests were performed with an iterative algorithm on array data structure with basic optimization
        - Small variations in performance metrics simulate the natural fluctuations seen in real benchmarks
        - This type of benchmark is useful for understanding scaling properties of a single algorithm configuration
        """,
    )
    return bench


if __name__ == "__main__":
    example_1_float_0_cat_in_2_out().report.show()
