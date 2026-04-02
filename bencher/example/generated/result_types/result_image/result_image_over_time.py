"""Auto-generated example: ResultImage: Over Time Slider."""

import bencher as bn
from datetime import datetime, timedelta
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


def example_result_image_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """ResultImage: Over Time Slider."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    benchable = PolygonRenderer()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, radius in enumerate([0.3, 0.6, 0.9]):
        benchable.radius = radius
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        bench.plot_sweep(
            "Image Over Time",
            input_vars=["sides"],
            result_vars=["polygon"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_result_image_over_time, level=3, over_time=True)
