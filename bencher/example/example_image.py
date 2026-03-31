import bencher as bn
import numpy as np
import math
from PIL import Image, ImageDraw


def polygon_points(radius: float, sides: int, start_angle: float):
    points = []
    for ang in np.linspace(0, 360, sides + 1):
        angle = math.radians(start_angle + ang)
        points.append(([math.sin(angle) * radius, math.cos(angle) * radius]))
    return points


class BenchPolygons(bn.ParametrizedSweep):
    sides = bn.IntSweep(default=3, bounds=(3, 7))
    radius = bn.FloatSweep(default=1, bounds=(0.2, 1))
    linewidth = bn.FloatSweep(default=1, bounds=(1, 10))
    color = bn.StringSweep(["red", "green", "blue"])
    start_angle = bn.FloatSweep(default=0, bounds=[0, 360])
    polygon = bn.ResultImage()
    area = bn.ResultVar()
    side_length = bn.ResultVar()

    def benchmark(self):
        points = polygon_points(self.radius, self.sides, self.start_angle)
        filepath = bn.gen_image_path("polygon")
        self.polygon = self.points_to_polygon_png(points, filepath)
        # Verify filepath is being returned
        assert isinstance(self.polygon, str), f"Expected string filepath, got {type(self.polygon)}"

        self.side_length = 2 * self.radius * math.sin(math.pi / self.sides)
        self.area = (self.sides * self.side_length**2) / (4 * math.tan(math.pi / self.sides))

    def points_to_polygon_png(self, points: list[float], filename: str):
        """Draw a closed polygon and save to png using PIL"""
        size = 300
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Scale points to image size (from [-1,1] to [0,size])
        scaled_points = [(((p[0] + 1) * size / 2), ((1 - p[1]) * size / 2)) for p in points]

        # Draw polygon outline
        draw.line(scaled_points, fill=self.color, width=int(self.linewidth))

        img.save(filename, "PNG")
        # Explicitly return the filename string
        return str(filename)


def example_image(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    run_cfg.cache_results = False
    bench = bn.Bench("polygons", BenchPolygons(), run_cfg=run_cfg)

    bench.result_vars = ["polygon", "area"]

    bench.add_plot_callback(bn.BenchResult.to_sweep_summary)
    # bench.add_plot_callback(bn.BenchResult.to_auto, level=2)
    bench.add_plot_callback(bn.BenchResult.to_panes, level=3)
    # bench.add_plot_callback(bn.BenchResult.to_panes)

    sweep_vars = ["sides", "radius", "linewidth", "color"]

    # sweep_vars = ["sides", "radius" ]

    for i in range(1, len(sweep_vars)):
        s = sweep_vars[:i]
        bench.plot_sweep(
            f"Polygons Sweeping {len(s)} Parameters",
            input_vars=s,
        )
        bench.report.append(bench.get_result().to_panes())

    return bench


if __name__ == "__main__":
    bn.run(example_image, level=3)
