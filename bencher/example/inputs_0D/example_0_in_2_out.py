"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bch
import random


class SimpleFloat0D(bch.ParametrizedSweep):
    """This class has 0 input dimensions and 2 output dimensions. It samples from Gaussian distributions"""

    # This defines a variable that we want to plot
    output1 = bch.ResultVar(units="ul", doc="a sample from a gaussian distribution")
    output2 = bch.ResultVar(units="ul", doc="a sample from a gaussian distribution")

    def __call__(self, **kwargs) -> dict:
        """Generate samples from Gaussian distributions

        Returns:
            dict: a dictionary with all the result variables in the ParametrisedSweep class as named key value pairs.
        """

        self.output1 = random.gauss(mu=0.0, sigma=1.0)
        self.output2 = random.gauss(mu=2.0, sigma=5.0)
        return super().__call__(**kwargs)


def example_0_in_2_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to sample a 0-dimensional variable (no input parameters)
    that produces two output values and plot the results.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    bench = SimpleFloat0D().to_bench(run_cfg, report)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    run_config = bch.BenchRunCfg(repeats=500)
    example_0_in_2_out(run_config).report.show()
