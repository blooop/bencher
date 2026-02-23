"""Rerun backend: 2D float + 2 categorical sweep example.

Demonstrates a higher-dimensional sweep with both float and categorical
dimensions. Categories become entity tree branches, and the remaining
float dimensions are logged as a 2D Tensor heatmap per category
combination. The blueprint creates nested Grid containers for each
categorical dimension with TensorView leaves:

    /algorithm_type/recursive/opt_level/O0/result   (TensorView)
    /algorithm_type/iterative/opt_level/O2/result   (TensorView)
    ...
"""

import math
import bencher as bch


class RerunFloatCat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, 2 * math.pi], doc="Input angle", units="rad", samples=20
    )
    amplitude = bch.FloatSweep(default=1, bounds=[0.5, 2.0], doc="Amplitude", units="ul", samples=5)
    algorithm_type = bch.StringSweep(["recursive", "iterative"], doc="Algorithm type")
    opt_level = bch.StringSweep(["O0", "O2"], doc="Optimization level")

    result = bch.ResultVar(units="v", doc="Computed output")
    cost = bch.ResultVar(units="ms", doc="Simulated compute cost")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        val = self.amplitude * math.sin(self.theta)
        algo_factor = 1.2 if self.algorithm_type == "recursive" else 0.8
        opt_factor = 0.6 if self.opt_level == "O2" else 1.0
        self.result = val * algo_factor
        self.cost = (abs(val) + 0.1) * algo_factor * opt_factor * 10.0
        return super().__call__(**kwargs)


def example_rerun_float_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """2D float + 2 cat → rerun: cats become entity branches, float dims logged as 2D Tensor heatmap."""
    bench = RerunFloatCat().to_bench(run_cfg)
    bench.plot_sweep(title="Rerun Float+Cat Example")
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    bench = example_rerun_float_cat(bch.BenchRunCfg(level=2))
    bench.get_result().to_rerun().show()
