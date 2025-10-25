"""This file contains examples for how to perform basic 2D benchmarking parameter sweeps"""

import math
import bencher as bch


class SimpleFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    offset = bch.FloatSweep(default=0, bounds=[0, 1], doc="Input angle offset", units="rad")
    noise = bch.FloatSweep(default=0, bounds=[0, 1], doc="noise", units="rad")
    out_sin = bch.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta) + self.offset + self.noise
        return super().__call__(**kwargs)


def example_2D_float_const(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = SimpleFloat().to_bench(run_cfg)
    const_vars = SimpleFloat().get_input_defaults_override(offset=0.5)
    bench.plot_sweep(input_vars=["theta"], const_vars=const_vars)

    const_vars = SimpleFloat().get_input_defaults_override(noise=0.2)
    bench.plot_sweep(input_vars=["theta"], const_vars=const_vars)

    bench.plot_sweep(input_vars=["theta"], const_vars=dict(offset=0.3))

    return bench


if __name__ == "__main__":
    example_2D_float_const().report.show()
