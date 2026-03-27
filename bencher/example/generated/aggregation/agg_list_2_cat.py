"""Auto-generated example: Aggregate 2 Categoricals (list)."""

from typing import Any

import bencher as bn


class GradientSurface(bn.ParametrizedSweep):
    """2D gradient surface with categorical direction and scale controls."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    y = bn.FloatSweep(default=0, bounds=[0, 1], doc="Y position")
    direction = bn.StringSweep(["diagonal", "horizontal", "vertical"], doc="Gradient direction")
    scale = bn.StringSweep(["linear", "quadratic", "sqrt"], doc="Gradient scale")

    out = bn.ResultVar(units="v", doc="Surface value")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        if self.direction == "diagonal":
            base = self.x + self.y
        elif self.direction == "horizontal":
            base = self.x
        else:
            base = self.y
        if self.scale == "linear":
            self.out = base
        elif self.scale == "quadratic":
            self.out = base**2
        else:
            self.out = base**0.5
        return super().__call__()


def example_agg_list_2_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate 2 Categoricals (list)."""
    bench = GradientSurface().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "y", "direction", "scale"],
        result_vars=["out"],
        description='Aggregate two categorical dimensions by name using aggregate=["direction", "scale"]. Both categoricals are averaged out, leaving a 2D heatmap of x vs y with mean and std computed across all direction/scale combinations.',
        post_description="The aggregated view shows a single heatmap because two float dimensions remain after collapsing both categoricals. The non-aggregated view below shows the full faceted heatmaps (one per direction × scale) — each with a visually distinct gradient pattern.",
        aggregate=["direction", "scale"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_list_2_cat, level=4)
