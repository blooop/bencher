"""Rerun backend: 2D float sweep example.

Demonstrates two FloatSweep dimensions mapped to two independent rerun
timelines. The viewer lets you scrub each axis independently to slice
through the 2D parameter space.
"""

import math
import bencher as bch


class Rerun2DFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=10
    )
    offset = bch.FloatSweep(default=0, bounds=[0, 1], doc="DC offset", units="v", samples=5)
    out_sin = bch.ResultVar(units="v", doc="sin(theta) + offset")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta) + self.offset
        return super().__call__(**kwargs)


def example_rerun_2D_float(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2D float sweep → rerun: theta and offset become independent timelines."""
    bench = Rerun2DFloat().to_bench(run_cfg)
    bench.plot_sweep(title="Rerun 2D Float Example")
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_2D_float(bch.BenchRunCfg(level=3))
    bench.get_result().to_rerun().show()
