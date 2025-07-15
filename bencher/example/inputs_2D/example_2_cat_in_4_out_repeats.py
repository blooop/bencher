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

    execution_time = bch.ResultVar(units="ms", doc="Execution time in milliseconds")
    memory_usage = bch.ResultVar(units="MB", doc="Memory usage in megabytes")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given inputs.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        # Base values that will be modified by language and environment
        base_execution = 0
        base_memory = 0

        # Different languages have different performance characteristics
        if self.language == "Python":
            base_execution = 150
            base_memory = 80
        elif self.language == "JavaScript":
            base_execution = 100
            base_memory = 60
        elif self.language == "Rust":
            base_execution = 20
            base_memory = 15
        elif self.language == "Go":
            base_execution = 40
            base_memory = 30

        # Environment affects performance
        if self.environment == "Development":
            # Dev environments have debugging overhead
            env_exec_modifier = 1.5
            env_mem_modifier = 1.3
        elif self.environment == "Testing":
            # Testing has moderate overhead
            env_exec_modifier = 1.2
            env_mem_modifier = 1.1
        else:  # Production
            # Production is optimized
            env_exec_modifier = 1.0
            env_mem_modifier = 1.0

        # Calculate final values with some randomness
        self.execution_time = base_execution * env_exec_modifier * random.uniform(0.9, 1.1)
        self.memory_usage = base_memory * env_mem_modifier * random.uniform(0.95, 1.05)

        return super().__call__(**kwargs)


def example_2_cat_in_4_out_repeats(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example compares performance metrics across programming languages and environments.

    It demonstrates how to sample categorical variables with multiple repeats
    and plot the results of two output variables.

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
        title="Programming Language and Environment Performance Metrics",
        description="Comparing execution time and memory usage across different programming languages and environments",
    )
    return bench


if __name__ == "__main__":
    example_2_cat_in_4_out_repeats().report.show()
