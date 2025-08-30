"""This file demonstrates benchmarking with categorical inputs and multiple outputs with repeats.

It simulates comparing programming languages and development environments, measuring
performance and developer productivity metrics.
"""

import random
import bencher as bch

random.seed(42)  # Fixed seed for reproducibility


class ProgrammingBenchmark(bch.ParametrizedSweep):
    """Benchmark class comparing programming languages and development environments."""

    language = bch.StringSweep(
        ["Python", "JavaScript", "Rust", "Go"], doc="Programming language being benchmarked"
    )
    environment = bch.StringSweep(
        ["Development", "Testing", "Production"], doc="Environment configuration"
    )

    data_size = bch.FloatSweep(bounds=[1, 1000], doc="Dataset size in MB to process")

    is_successful = bch.ResultBool(doc="Whether the benchmark run was successful")
    execution_time = bch.ResultVar(units="ms", doc="Code execution time in milliseconds")
    memory_usage = bch.ResultVar(units="MB", doc="Peak memory usage in megabytes")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given inputs.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        # Execution time varies by language (lower is better)
        base_execution_times = {
            "Python": 120.0,  # Slower interpreted language
            "JavaScript": 80.0,  # V8 optimizations help
            "Rust": 25.0,  # Fast compiled language
            "Go": 35.0,  # Fast with good concurrency
        }

        # Memory usage varies by language (lower is better)
        base_memory_usage = {
            "Python": 45.0,  # High due to interpreter overhead
            "JavaScript": 35.0,  # V8 heap management
            "Rust": 12.0,  # Efficient memory management
            "Go": 18.0,  # Garbage collector overhead
        }

        # Environment affects performance
        if self.environment == "Development":
            time_modifier = 1.3  # Debug builds, more logging
            memory_modifier = 1.4  # Debug symbols, profiling overhead
        elif self.environment == "Testing":
            time_modifier = 1.1  # Some test overhead
            memory_modifier = 1.2  # Test frameworks loaded
        else:  # Production
            time_modifier = 1.0  # Optimized builds
            memory_modifier = 1.0  # Minimal overhead

        # Calculate realistic metrics with variability
        self.execution_time = (
            base_execution_times[self.language] * time_modifier * random.uniform(0.8, 1.2)
        )

        self.memory_usage = (
            base_memory_usage[self.language] * memory_modifier * random.uniform(0.85, 1.15)
        )

        # Success based on reasonable performance thresholds
        time_threshold = 100.0  # ms
        memory_threshold = 40.0  # MB
        self.is_successful = (
            self.execution_time < time_threshold and self.memory_usage < memory_threshold
        )

        return super().__call__(**kwargs)


def example_2_cat_in_4_out_repeats(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example compares a boolean and a float result across programming languages and environments.

    It demonstrates how to sample categorical variables with multiple repeats
    and plot the results of a boolean and a float output variable.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 15  # Run multiple times to get statistical significance
    bench = ProgrammingBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        input_vars=["language", "environment"],
        title="Programming Language and Environment: Boolean and Float Results",
        description="Comparing a boolean (success) and a float (score) result across different programming languages and environments",
    )

    bench.plot_sweep(
        input_vars=["float1"],
        title="Programming Language and Environment: Boolean and Float Results",
        description="Comparing a boolean (success) and a float (score) result across different programming languages and environments",
    )

    # bench.report.append(res.to_line())

    return bench


if __name__ == "__main__":
    example_2_cat_in_4_out_repeats().report.show()
