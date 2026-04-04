"""Auto-generated example: ResultImage: Progressive Multi-Parameter Sweep."""

import bencher as bn
import math
import numpy as np
from PIL import Image, ImageDraw


def _polygon_points(radius, sides, start_angle=0.0):
    points = []
    for ang in np.linspace(0, 360, sides + 1):
        angle = math.radians(start_angle + ang)
        points.append([math.sin(angle) * radius, math.cos(angle) * radius])
    return points


def _draw_polygon_image(points, color, linewidth, size=200):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scaled = [((p[0] + 1) * size / 2, (1 - p[1]) * size / 2) for p in points]
    draw.line(scaled, fill=color, width=int(linewidth))
    return img


class PolygonRenderer(bn.ParametrizedSweep):
    """Renders polygon images with configurable sides, radius, and color."""

    sides = bn.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    radius = bn.FloatSweep(default=0.6, bounds=(0.2, 1.0), doc="Polygon radius")
    color = bn.StringSweep(["red", "green", "blue"], doc="Line color")
    polygon = bn.ResultImage(doc="Rendered polygon image")
    area = bn.ResultFloat("u^2", doc="Polygon area")

    def benchmark(self):
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color, linewidth=3)
        filepath = bn.gen_image_path("polygon")
        img.save(filepath, "PNG")
        self.polygon = str(filepath)
        self.area = (self.sides * (2 * self.radius * math.sin(math.pi / self.sides)) ** 2) / (
            4 * math.tan(math.pi / self.sides)
        )


def example_result_image_progressive(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """ResultImage: Progressive Multi-Parameter Sweep."""
    bench = PolygonRenderer().to_bench(run_cfg)
    bench.add_plot_callback(bn.BenchResult.to_sweep_summary)
    bench.add_plot_callback(bn.BenchResult.to_panes, level=3)
    sweep_vars = ["sides", "radius", "color"]
    for i in range(1, len(sweep_vars) + 1):
        bench.plot_sweep(
            f"Polygons Sweeping {i} Parameter(s)",
            input_vars=sweep_vars[:i],
            result_vars=["polygon", "area"],
        )

    return bench


if __name__ == "__main__":
    bn.run(example_result_image_progressive, level=3)
