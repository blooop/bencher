"""Auto-generated example: Aggregate to 1-D (True)."""

from typing import Any

import bencher as bn


class GradientScale(bn.ParametrizedSweep):
    """1D gradient with categorical scale control."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultVar(units="v", doc="Surface value")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        if self.scale == "linear":
            self.out = self.x
        elif self.scale == "quadratic":
            self.out = self.x**2
        else:
            self.out = self.x**0.5
        return super().__call__()


def example_agg_all(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate to 1-D (True)."""
    bench = GradientScale().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "scale"],
        result_vars=["out"],
        description="Setting aggregate=True collapses all but the first input dimension, reducing the sweep to a 1-D plot. Useful when you want a simple curve from a multi-dimensional sweep.",
        post_description="The aggregated view collapses all inputs except the first into a single mean ± std curve. The non-aggregated view below shows the full detail.",
        aggregate=True,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_all, level=4)
