"""Example demonstrating ResultBool plotting with bar charts.

This example shows how boolean success/failure results are displayed
both with and without repeats.
"""

import bencher as bch
from bencher.example.example_cat2_scatter_jitter import ProgrammingBenchmark


class SimpleBoolBenchmark(bch.ParametrizedSweep):
    """Simple benchmark class that generates deterministic boolean results."""

    threshold = bch.FloatSweep(default=0.5, bounds=[0.1, 0.9], doc="Threshold value for success")
    complexity = bch.IntSweep(default=5, bounds=[1, 10], doc="Complexity level")

    is_successful = bch.ResultBool(doc="Whether the operation was successful")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given inputs.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        # Deterministic boolean result based on parameters
        # Success when complexity is low relative to threshold
        success_probability = 1.0 - (self.complexity / 10.0)
        self.is_successful = success_probability > self.threshold

        return super().__call__(**kwargs)


def example_bool_result_no_repeats(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example showing boolean result visualization without repeats.

    This demonstrates how ResultBool values work with no repetition:
    1. Single boolean value per parameter combination
    2. Displayed as binary success/failure in bar charts

    Args:
        run_cfg: Configuration for the benchmark run

    Returns:
        bch.Bench: The benchmark object with results
    """
    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    # Explicitly set repeats to 1 to avoid averaging
    run_cfg.repeats = 1

    bench = SimpleBoolBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["threshold"],
        result_vars=["is_successful"],
        title="Success vs Threshold (No Repeats)",
        description="Boolean success/failure for different threshold values without averaging",
    )
    bench.plot_sweep(
        input_vars=["complexity"],
        result_vars=["is_successful"],
        title="Success vs Threshold (No Repeats)",
        description="Boolean success/failure for different threshold values without averaging",
    )

    return bench


def example_bool_result_categorical_no_repeats(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example showing boolean result visualization with categorical variables and no repeats.

    This demonstrates how ResultBool values work with categorical inputs without averaging:
    1. Single boolean value per category (no repeats)
    2. Displayed as binary success/failure in bar charts

    Args:
        run_cfg: Configuration for the benchmark run

    Returns:
        bch.Bench: The benchmark object with results
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()

    # Explicitly set repeats to 1 to avoid averaging
    run_cfg.repeats = 1

    bench = ProgrammingBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["language"],
        result_vars=["is_successful"],
        title="Programming Success by Language (No Repeats)",
        description="Boolean success/failure by programming language without averaging",
    )

    return bench


def example_bool_result_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example showing boolean result visualization with 1 input dimension.

    This demonstrates how ResultBool values work with single input:
    1. Collected over multiple repeats for each threshold
    2. Automatically averaged to show success rates (0.0 to 1.0)

    Args:
        run_cfg: Configuration for the benchmark run

    Returns:
        bch.Bench: The benchmark object with results
    """

    bench = ProgrammingBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["language"],
        result_vars=["is_successful"],
        title="Programming Success Rate by Language",
        description="Boolean success rates by programming language",
    )

    return bench


def example_bool_result_2d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Example showing boolean result visualization with 2 input dimensions.

    This demonstrates how ResultBool values work with two categorical inputs:
    1. Collected over multiple repeats for each programming language/environment combination
    2. Automatically averaged to show success rates (0.0 to 1.0)

    Args:
        run_cfg: Configuration for the benchmark run

    Returns:
        bch.Bench: The benchmark object with results
    """

    bench = ProgrammingBenchmark().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["language", "environment"],
        result_vars=["is_successful"],
        title="Programming Success Rate by Language and Environment",
        description="Boolean success rates by programming language and environment",
    )

    return bench


if __name__ == "__main__":
    bench_runner = bch.BenchRunner()
    bench_runner.add(example_bool_result_no_repeats)
    bench_runner.add(example_bool_result_categorical_no_repeats)
    bench_runner.add(example_bool_result_1d)
    bench_runner.add(example_bool_result_2d)
    bench_runner.run(level=5, repeats=100, show=True, grouped=True)
