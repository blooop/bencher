"""This file contains examples for how to perform basic 2D benchmarking parameter sweeps"""

import math
import bencher as bch


class SimpleFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    offset = bch.FloatSweep(default=0, bounds=[0, 1], doc="Input angle", units="rad")
    out_sin = bch.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta) + self.offset
        return super().__call__(**kwargs)


def example_2D_float(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = SimpleFloat().to_bench(run_cfg, report)
    res = bench.plot_sweep()

    bench.add(bch.CurveResult)
    bench.report.append(res.to(bch.CurveResult))
    bench.report.append(res.to(bch.HeatmapResult))
    bench.add(bch.BarResult)
    return bench


if __name__ == "__main__":
    example_2D_float().report.show()
