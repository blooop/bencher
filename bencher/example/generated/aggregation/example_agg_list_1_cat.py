"""Auto-generated example: Aggregate by Name (list)."""

import bencher as bn


class GradientDirection(bn.ParametrizedSweep):
    """2D gradient surface controlled by direction."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    y = bn.FloatSweep(default=0, bounds=[0, 1], doc="Y position")
    direction = bn.StringSweep(["diagonal", "horizontal", "vertical"], doc="Gradient direction")

    out = bn.ResultFloat(units="v", doc="Surface value")

    def benchmark(self):
        if self.direction == "diagonal":
            self.out = self.x + self.y
        elif self.direction == "horizontal":
            self.out = self.x
        else:
            self.out = self.y


def example_agg_list_1_cat(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate by Name (list)."""
    bench = GradientDirection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "y", "direction"],
        result_vars=["out"],
        description='Aggregate a specific dimension by name using aggregate=["direction"]. The direction categorical is averaged out, leaving a 2D heatmap of x vs y. This is the most explicit form — you list exactly which dimensions to collapse.',
        post_description="The aggregated view shows a heatmap because two float dimensions remain after collapsing direction. The non-aggregated view below shows the full faceted heatmaps (one per direction).",
        aggregate=["direction"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_list_1_cat, level=4)
