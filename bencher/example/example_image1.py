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
    linestyle = bn.StringSweep(["solid", "dashed", "dotted"])
    color = bn.StringSweep(["red", "green", "blue"])
    start_angle = bn.FloatSweep(default=0, bounds=[0, 360])
    polygon = bn.ResultImage()
    polygon_small = bn.ResultImage()

    area = bn.ResultVar()
    side_length = bn.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = polygon_points(self.radius, self.sides, self.start_angle)
        filepath = bn.gen_image_path("polygon")
        self.polygon = self.points_to_polygon_png(points, filepath, dpi=30)
        self.polygon_small = self.points_to_polygon_png(
            points, bn.gen_image_path("polygon"), dpi=10
        )
        # Verify filepaths are being returned
        assert isinstance(self.polygon, str), f"Expected string filepath, got {type(self.polygon)}"
        assert isinstance(self.polygon_small, str), (
            f"Expected string filepath, got {type(self.polygon_small)}"
        )

        self.side_length = 2 * self.radius * math.sin(math.pi / self.sides)
        self.area = (self.sides * self.side_length**2) / (4 * math.tan(math.pi / self.sides))
        return super().__call__()

    def points_to_polygon_png(self, points: list[float], filename: str, dpi):
        """Draw a closed polygon and save to png using PIL"""
        size = int(100 * (dpi / 30))
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        scaled_points = [(((p[0] + 1) * size / 2), ((1 - p[1]) * size / 2)) for p in points]
        draw.line(scaled_points, fill=self.color, width=int(self.linewidth))

        img.save(filename, "PNG")
        return str(filename)


def example_image_vid_sequential1(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchPolygons().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["sides"])

    bench.report.append(res.to_panes(zip_results=True))

    return bench


if __name__ == "__main__":
    ex_run_cfg = bn.BenchRunCfg()
    ex_run_cfg.cache_samples = True
    ex_run_cfg.overwrite_sample_cache = True
    bn.run(example_image_vid_sequential1, level=3, run_cfg=ex_run_cfg)
