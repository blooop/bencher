"""This file contains examples for how to perform basic 2D benchmarking parameter sweeps"""

import math
import bencher as bn


class SimpleFloat(bn.ParametrizedSweep):
    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    offset = bn.FloatSweep(default=0, bounds=[0, 1], doc="Input angle", units="rad")
    out_sin = bn.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta) + self.offset
        return super().__call__(**kwargs)


def example_2D_float(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = SimpleFloat().to_bench(run_cfg)
    res = bench.plot_sweep()

    bench.add(bn.CurveResult)
    bench.report.append(res.to(bn.CurveResult))
    bench.report.append(res.to(bn.HeatmapResult))
    bench.add(bn.BarResult)
    return bench


if __name__ == "__main__":
    bn.run(example_2D_float)
