"""This file has some examples for how to perform basic benchmarking parameter sweeps"""

import math
import bencher as bn


class SimpleFloat(bn.ParametrizedSweep):
    theta = bn.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bn.ResultFloat(units="v", doc="sin of theta")

    def benchmark(self):
        self.out_sin = math.sin(self.theta)


def example_simple_float(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = SimpleFloat().to_bench(run_cfg)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    bn.run(example_simple_float)
