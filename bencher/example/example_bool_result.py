"""Example demonstrating ResultBool plotting with clean bar charts.

This example shows how boolean success/failure results are properly averaged
over multiple repeats and displayed as success rates in a clean bar chart.
"""

import bencher as bch
from bencher.example.example_cat2_scatter_jitter import ProgrammingBenchmark


def example_bool_result_1d(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing clean boolean result visualization with 1 input dimension.

    This demonstrates how ResultBool values work with single categorical input:
    1. Collected over multiple repeats for each programming language
    2. Automatically averaged to show success rates (0.0 to 1.0)

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object with results
    """

    bench = ProgrammingBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        input_vars=["language"],
        result_vars=["is_successful"],
        title="Programming Success Rate by Language (1D)",
        description="Boolean success rates by programming language only, displayed as clean bars",
    )

    return bench


def example_bool_result_2d(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing clean boolean result visualization.

    This demonstrates how ResultBool values are:
    1. Collected over multiple repeats for each programming language/environment
    2. Automatically averaged to show success rates (0.0 to 1.0)

    The fix ensures that boolean results don't create multi-level groupings
    or show variable names under each bar.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object with results
    """

    bench = ProgrammingBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep(
        input_vars=["language", "environment"],
        result_vars=["is_successful"],
        title="Programming Success Rate by Language and Environment",
        description="Boolean success rates averaged over multiple runs, displayed as clean bars without unwanted groupings",
    )

    return bench


if __name__ == "__main__":
    bench_runner = bch.BenchRunner()
    bench_runner.add(example_bool_result_1d)
    bench_runner.add(example_bool_result_2d)
    bench_runner.run(level=5, repeats=100, show=True, grouped=True)
