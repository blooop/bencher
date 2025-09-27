import bencher as bch


class Square(bch.ParametrizedSweep):
    """An example of a datatype with an integer and float parameter"""

    x = bch.FloatSweep(default=0, bounds=[0, 6])

    result = bch.ResultVar("ul", doc="Square of x")

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.result = self.x * self.x
        return self.get_results_values_as_dict()


def example_custom_sweep2(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """This example shows how to define a custom set of value to sample from instead of a uniform sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """

    bench = Square().to_bench(run_cfg=run_cfg, report=report)

    # These are all equivalent
    bench.plot_sweep(input_vars=[Square.param.x.with_sample_values([0, 1, 2])])
    bench.plot_sweep(input_vars=[bch.p("x", [0, 1, 2])])
    bench.plot_sweep(input_vars=[bch.p("x", [4, 5, 6])])

    bench.plot_sweep(input_vars=[bch.p("x", samples=5)])
    bench.plot_sweep(input_vars=[bch.p("x", samples=6)])

    return bench


if __name__ == "__main__":
    example_custom_sweep2().report.show()
