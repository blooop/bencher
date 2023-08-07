import random

import bencher as bch


class GaussianDist(bch.ParametrizedSweep):
    """A class to represent a gaussian distribution."""

    mean = bch.FloatSweep(
        default=0, bounds=[-1.0, 1.0], doc="mean of the gaussian distribution", samples=3
    )
    sigma = bch.FloatSweep(
        default=1, bounds=[0, 1.0], doc="standard deviation of gaussian distribution", samples=4
    )


class Example2DGaussianResult(bch.ParametrizedSweep):
    """A class to represent the properties of a volume sample."""

    gauss_x = bch.ResultVar("m", doc="x value of the 2D gaussian")
    gauss_y = bch.ResultVar("m", doc="y value of the 2D gaussian")

    point2D = bch.ResultVec(2, "m", doc="2D vector of the point")


def bench_fn(dist: GaussianDist) -> Example2DGaussianResult:
    """This function samples a point from a gaussian distribution.

    Args:
        dist (GaussianDist): Sample point

    Returns:
        Example2DGaussianResult: Value at that point
    """
    output = Example2DGaussianResult()

    output.gauss_x = random.gauss(dist.mean, dist.sigma)
    output.gauss_y = random.gauss(dist.mean, dist.sigma)
    output.point2D = [output.gauss_x, output.gauss_y]

    return output


def example_floats2D_scatter(run_cfg: bch.BenchRunCfg) -> bch.Bench:
    """Example of how to perform a 3D floating point parameter sweep

    Args:
        run_cfg (BenchRunCfg): configuration of how to perform the param sweep

    Returns:
        Bench: results of the parameter sweep
    """
    bench = bch.Bench(
        "Bencher_Example_Floats_Scatter", bench_fn, GaussianDist, plot_lib=bch.PlotLibrary.default()
    )

    bench.plot_sweep(
        result_vars=[
            Example2DGaussianResult.param.point2D,
            # Example2DGaussianResult.param.gauss_x,
            # Example2DGaussianResult.param.gauss_y,
        ],
        title="Float 2D Scatter Example",
        run_cfg=run_cfg,
    )

    bench.plot_sweep(
        input_vars=[GaussianDist.param.mean],
        result_vars=[
            Example2DGaussianResult.param.point2D,
            # Example2DGaussianResult.param.gauss_x,
            # Example2DGaussianResult.param.gauss_y,
        ],
        title="Float 2D Scatter With Changing Mean",
        run_cfg=run_cfg,
    )

    bench.plot_sweep(
        input_vars=[GaussianDist.param.sigma],
        result_vars=[
            Example2DGaussianResult.param.point2D,
            # Example2DGaussianResult.param.gauss_x,
            # Example2DGaussianResult.param.gauss_y,
        ],
        title="Float 2D Scatter With Changing Sigma",
        run_cfg=run_cfg,
    )

    # future work
    # bench.plot_sweep(
    #     input_vars=[GaussianDist.param.mean, GaussianDist.param.sigma],
    #     result_vars=[
    #         GaussianResult.param.point2D,
    #         GaussianResult.param.gauss_x,
    #         GaussianResult.param.gauss_y,
    #     ],
    #     title="Float 2D Scatter With Changing Sigma",
    #     run_cfg=run_cfg,
    # )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.repeats = 50
    ex_run_cfg.over_time = True
    # ex_run_cfg.clear_history = True
    example_floats2D_scatter(ex_run_cfg).show()
