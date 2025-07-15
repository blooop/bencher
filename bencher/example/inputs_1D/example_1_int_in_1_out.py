"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bch


class DataSource:
    """A simple data source class that provides access to predefined data points."""

    def __init__(self):
        """Initialize the data source with predefined values and call counts."""
        self.data = [
            [0, 0, 0, 0],
            [1, 1, 1, 1],
            [1, 1, 1, 1],
            [2, 1, 1, 0],
            [2, 2, 0, 0],
            [2, 2, 1, 1],
        ]

        self.call_count = [0] * len(self.data)

    def call(self, index: int, repeat: int = None) -> int:
        """Retrieve a data point at the specified index and repeat count.

        Args:
            index: The index of the data row to access
            repeat: The specific repeat count to use. If None, uses and increments internal counter

        Returns:
            int: The value at the specified index and repeat position
        """
        if repeat is None:
            self.call_count[index] += 1
            repeat = self.call_count[index]
        print(index, repeat)
        return self.data[index][repeat - 1]


class Example1D(bch.ParametrizedSweep):
    """Example 1D parameter sweep class with one input dimension and one output dimension."""

    index = bch.IntSweep(default=0, bounds=[0, 5], doc="Input index", units="rad", samples=30)
    output = bch.ResultVar(units="v", doc="Output value from data source")

    def __init__(self, **params):
        """Initialize the Example1D sweep with a data source.

        Args:
            **params: Parameters to pass to the parent class constructor
        """
        super().__init__(**params)
        self.data1 = DataSource()

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given parameters.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the output of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)
        self.output = self.data1.call(self.index)
        return super().__call__(**kwargs)


def example_1_int_in_1_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to sample a 1-dimensional integer variable and plot
    the result of that parameter sweep.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """
    bench = Example1D().to_bench(run_cfg, report)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    run_config = bch.BenchRunCfg()
    report_obj = bch.BenchReport()
    example_1_int_in_1_out(run_config, report_obj)

    run_config.repeats = 4
    example_1_int_in_1_out(run_config, report_obj)

    # run_cfg.over_time = True
    # for i in range(4):
    #     example_1_in_2_out(run_cfg, report_obj)

    report_obj.show()
