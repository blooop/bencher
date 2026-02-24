"""Rerun backend: 0D example (no inputs, scalar outputs only).

Demonstrates logging scalar results with no sweep dimensions.
The rerun viewer shows the raw scalar values as static entities.
"""

import random
import bencher as bch

random.seed(42)


class Rerun0D(bch.ParametrizedSweep):
    output1 = bch.ResultVar(units="ul", doc="sample from gaussian(0, 1)")
    output2 = bch.ResultVar(units="ul", doc="sample from gaussian(2, 5)")

    def __call__(self, **kwargs) -> dict:
        self.update_params_from_kwargs(**kwargs)
        self.output1 = random.gauss(mu=0.0, sigma=1.0)
        self.output2 = random.gauss(mu=2.0, sigma=5.0)
        return super().__call__(**kwargs)


def example_rerun_0D(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0D benchmark → rerun: scalar values logged as static entities."""
    bench = Rerun0D().to_bench(run_cfg)
    bench.plot_sweep(title="Rerun 0D Example")
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    example_rerun_0D(bch.BenchRunCfg(repeats=1, backend=bch.RenderBackend.rerun)).report.show()
