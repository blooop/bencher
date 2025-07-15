"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import bencher as bch
import random


class SimpleFloat0D(bch.ParametrizedSweep):
    """This class has 0 input dimensions and 1 output dimension. It samples from a Gaussian distribution"""

    # This defines a variable that we want to plot
    output = bch.ResultVar(units="ul", doc="a sample from a gaussian distribution")

    def __call__(self, **kwargs) -> dict:
        """Generate a sample from a Gaussian distribution

        Returns:
            dict: a dictionary with all the result variables in the ParametrisedSweep class as named key value pairs.
        """

        self.output = random.gauss(mu=0.0, sigma=1.0)
        return super().__call__(**kwargs)


def example_0_in_1_out(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to sample a 0-dimensional variable (no input parameters)
    and plot the result of that sampling operation.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    bench = SimpleFloat0D().to_bench(run_cfg, report)
    bench.plot_sweep()

    bench.add(bch.TableResult)
    return bench


if __name__ == "__main__":
    example_0_in_1_out().report.show()
    # run_config = bch.BenchRunCfg(repeats=100)
    # report_obj = bch.BenchReport()
    # example_0_in_1_out(run_config, report_obj).report.show()

    # run_cfg.over_time = True
    # run_cfg.cache_samples = True
    # for i in range(4):
    #     example_0_in_1_out(run_cfg, report_obj)

    # run_config.over_time = True
    # run_config.auto_plot = False
    # for _ in range(4):
    #     example_0_in_1_out(run_config, report_obj)

    # run_config.auto_plot = True
    # example_0_in_1_out(run_config, report_obj)

    # report_obj.show()
