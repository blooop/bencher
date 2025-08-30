"""Example demonstrating ResultBool plotting with clean bar charts.

This example shows how boolean success/failure results are properly averaged
over multiple repeats and displayed as success rates in a clean bar chart.
"""

import random
import bencher as bch

random.seed(42)  # Fixed seed for reproducibility


class SystemBenchmark(bch.ParametrizedSweep):
    """Benchmark class testing different system configurations."""

    system_type = bch.StringSweep(
        ["Server", "Desktop", "Mobile", "Embedded"], doc="Type of system being tested"
    )

    task_completed = bch.ResultBool(doc="Whether the benchmark task completed successfully")

    def __call__(self, **kwargs) -> dict:
        """Execute the benchmark for the given system type.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the benchmark results
        """
        self.update_params_from_kwargs(**kwargs)

        # Simulate different success rates based on system type
        success_rates = {
            "Server": 0.95,  # Servers are very reliable
            "Desktop": 0.85,  # Desktops are fairly reliable
            "Mobile": 0.70,  # Mobile devices have more constraints
            "Embedded": 0.60,  # Embedded systems have limited resources
        }

        base_rate = success_rates[self.system_type]
        # Add some randomness to simulate real-world variability
        actual_rate = base_rate + random.uniform(-0.1, 0.1)

        # Boolean result: success based on the probability
        self.task_completed = random.random() < actual_rate

        return super().__call__(**kwargs)


def example_bool_result_clean_bars(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing clean boolean result visualization.

    This demonstrates how ResultBool values are:
    1. Collected over multiple repeats for each system type
    2. Automatically averaged to show success rates (0.0 to 1.0)
    3. Displayed as clean bar charts without unwanted sub-labels

    The fix ensures that boolean results don't create multi-level groupings
    or show variable names under each bar.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object with results
    """

    bench = SystemBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        input_vars=["system_type"],
        result_vars=["task_completed"],
        title="System Reliability: Task Completion Success Rate",
        description="Boolean success rates averaged over multiple runs, displayed as clean bars without unwanted groupings",
    )

    return bench


if __name__ == "__main__":
    example_bool_result_clean_bars().report.show()
