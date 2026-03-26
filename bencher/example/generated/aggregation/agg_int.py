"""Auto-generated example: Aggregate Last N (int)."""

from typing import Any

import bencher as bn


class GradientDirectionScale(bn.ParametrizedSweep):
    """1D gradient with categorical direction and scale controls."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    direction = bn.StringSweep(["positive", "negative", "symmetric"], doc="Gradient direction")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultVar(units="v", doc="Surface value")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        if self.direction == "positive":
            base = self.x
        elif self.direction == "negative":
            base = 1.0 - self.x
        else:
            base = abs(2.0 * self.x - 1.0)
        if self.scale == "linear":
            self.out = base
        elif self.scale == "quadratic":
            self.out = base**2
        else:
            self.out = base**0.5
        return super().__call__()


def example_agg_int(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate Last N (int)."""
    bench = GradientDirectionScale().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "direction", "scale"],
        result_vars=["out"],
        description="Setting aggregate=1 collapses the last 1 input dimension (scale). The remaining dimensions (x, direction) produce a line plot faceted by direction.",
        post_description="The aggregated view averages over the scale dimension. Use aggregate=N to collapse the last N dimensions in the input variable list.",
        aggregate=1,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_int, level=4)
