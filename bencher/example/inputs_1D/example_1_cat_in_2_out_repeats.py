"""This file demonstrates benchmarking with categorical inputs and multiple outputs with repeats."""

import random
import bencher as bch

random.seed(0)


class DataStructureBenchmark(bch.ParametrizedSweep):
    """Example class for comparing different data structure operations with two output variables."""

    operation = bch.StringSweep(
        ["list_append", "dict_insert"],
        doc="Type of data structure operation to benchmark",
    )
    execution_time = bch.ResultVar(units="ms", doc="Time taken to complete operations")
    memory_usage = bch.ResultVar(units="KB", doc="Memory used by the operation")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given data structure operation.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        # Simple simulations of different data structure operations
        # In a real benchmark, you would implement or measure actual operations

        if self.operation == "list_append":
            # List append operations (typically fast for adding elements)
            self.execution_time = random.gauss(mu=5.0, sigma=1.0)
            self.memory_usage = random.gauss(mu=120.0, sigma=20.0)
        elif self.operation == "dict_insert":
            # Dictionary insertions (hash table operations)
            self.execution_time = random.gauss(mu=6.5, sigma=1.2)
            self.memory_usage = random.gauss(mu=180.0, sigma=25.0)

        return super().__call__(**kwargs)


def example_1_cat_in_2_out_repeats(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to benchmark different data structure operations with multiple repeats
    and plot the results of execution time and memory usage.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 30  # Increased repeats for better statistical significance
    bench = DataStructureBenchmark().to_bench(run_cfg, report)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    example_1_cat_in_2_out_repeats().report.show()
