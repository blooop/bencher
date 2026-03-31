"""Auto-generated example: Aggregate with Max."""

import bencher as bn


class GradientDirection(bn.ParametrizedSweep):
    """2D gradient surface controlled by direction."""

    x = bn.FloatSweep(default=0, bounds=[0, 1], doc="X position")
    y = bn.FloatSweep(default=0, bounds=[0, 1], doc="Y position")
    direction = bn.StringSweep(["diagonal", "horizontal", "vertical"], doc="Gradient direction")

    out = bn.ResultVar(units="v", doc="Surface value")

    def benchmark(self):
        if self.direction == "diagonal":
            self.out = self.x + self.y
        elif self.direction == "horizontal":
            self.out = self.x
        else:
            self.out = self.y


def example_agg_fn_max(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate with Max."""
    bench = GradientDirection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["x", "y", "direction"],
        result_vars=["out"],
        description='Combine aggregate=["direction"] with agg_fn="max" to show the maximum surface value across directions for each (x, y) combination.',
        post_description='Unlike the default mean aggregation, agg_fn="max" picks the highest direction at every point. Other options: "min", "sum", "median".',
        aggregate=["direction"],
        agg_fn="max",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_agg_fn_max, level=4)
