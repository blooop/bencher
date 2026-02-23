"""Rerun backend: 1D float sweep displayed as a line graph in TimeSeriesView.

The single FloatSweep dimension is iterated as the ``log_tick`` timeline with
``rr.Scalars`` at each step, producing a line graph.  The blueprint arranges
one TimeSeriesView per result variable in a Vertical container.
"""

import math
import bencher as bch


class Rerun1DFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, 2 * math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bch.ResultVar(units="v", doc="sin of theta")
    out_cos = bch.ResultVar(units="v", doc="cos of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        self.out_cos = math.cos(self.theta)
        return super().__call__(**kwargs)


def example_rerun_1D_float(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """1D float sweep → rerun: displayed as line graphs via TimeSeriesView."""
    bench = Rerun1DFloat().to_bench(run_cfg)
    bench.plot_sweep(title="Rerun 1D Float Example")
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_1D_float(bch.BenchRunCfg(level=5))
    bench.get_result().to_rerun().show()
