"""This file demonstrates benchmarking with categorical inputs and multiple outputs with repeats."""

import random
import bencher as bch

random.seed(0)


class ExampleCat1D(bch.ParametrizedSweep):
    """Example class for categorical parameter sweep with two output variables."""

    population = bch.StringSweep(["population1", "population2"], doc="Distribution to sample from")
    age = bch.ResultVar(units="v", doc="Age of individual from population")
    children = bch.ResultVar(units="v", doc="Number of children of individual from population")

    def __call__(self, **kwargs) -> dict:
        """Execute the parameter sweep for the given population.

        Args:
            **kwargs: Additional parameters to update before executing

        Returns:
            dict: Dictionary containing the outputs of the parameter sweep
        """
        self.update_params_from_kwargs(**kwargs)

        if self.population == "population1":
            self.age = random.gauss(mu=50.0, sigma=10.0)
            self.children = random.gauss(mu=1.5, sigma=0.5)
        else:
            self.age = random.gauss(mu=60, sigma=20)
            self.children = random.gauss(mu=3.0, sigma=1.0)

        return super().__call__(**kwargs)


def example_1_cat_in_2_out_repeats(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to sample a 1-dimensional categorical variable with multiple repeats
    and plot the result of two output variables from that parameter sweep.

    Args:
        run_cfg: Configuration for the benchmark run
        report: Report to append the results to

    Returns:
        bch.Bench: The benchmark object
    """

    if run_cfg is None:
        run_cfg = bch.BenchRunCfg()
    run_cfg.repeats = 20
    bench = ExampleCat1D().to_bench(run_cfg, report)
    bench.plot_sweep()
    bench.report.append(bench.get_result().to_violin())

    return bench


if __name__ == "__main__":
    example_1_cat_in_2_out_repeats().report.show()
