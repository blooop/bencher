"""Auto-generated example: Plot Type: Surface."""

import bencher as bn

import math


class SurfaceDemo(bn.ParametrizedSweep):
    """3D surface of a trigonometric function."""

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Surface height")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)


def example_plot_surface(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Surface."""
    bench = SurfaceDemo().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["x", "y"], result_vars=["distance"])
    bench.report.append(res.to_surface())

    return bench


if __name__ == "__main__":
    bn.run(example_plot_surface, level=2)
