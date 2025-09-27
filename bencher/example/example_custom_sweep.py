import bencher as bch


class Square(bch.ParametrizedSweep):
    """An example of a datatype with an integer and float parameter"""

    x = bch.FloatSweep(
        sample_values=[2, 3, 4, 7, 8, 9],
        doc="An example of a user defines set of sweep values",
    )
    y = bch.IntSweep(
        sample_values=[1, 2, 6], doc="An example of a user defines set of sweep values"
    )

    result = bch.ResultVar("ul", doc="Square of x")

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.x * self.x * self.y * 3
        return self.get_results_values_as_dict()


def example_custom_sweep(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to define a custom set of value to sample from instead of a uniform sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """

    bencher = bch.Bench(
        "benchmarking_example_custom_sweep", Square(), run_cfg=run_cfg, report=report
    )
    # bencher = bch.Bench("benchmarking_example_custom_sweep", call,run_cfg=run_cfg)

    # here we sample the input variable theta and plot the value of output1. The (noisy) function is sampled 20 times so you can see the distribution

    bencher.plot_sweep(
        title="Example User Defined Sweep 1D",
        input_vars=["x"],
        result_vars=["result"],
        description="Sample the x parameter",
    )

    bencher.plot_sweep(
        title="Example User Defined Sweep 2D",
        description="By default bencher sweep all the variables in a class",
    )

    return bencher


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg(run_tag="example_tag1", print_meta=True)
    example_custom_sweep(ex_run_cfg).report.show()
