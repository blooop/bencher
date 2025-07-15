import bencher as bch
import numpy as np
import math
from PIL import Image, ImageDraw


def polygon_points(radius: float, sides: int, start_angle: float):
    points = []
    for ang in np.linspace(0, 360, sides + 1):
        angle = math.radians(start_angle + ang)
        points.append(([math.sin(angle) * radius, math.cos(angle) * radius]))
    return points


class BenchPolygons(bch.ParametrizedSweep):
    sides = bch.IntSweep(default=3, bounds=(3, 7))
    radius = bch.FloatSweep(default=1, bounds=(0.2, 1))
    linewidth = bch.FloatSweep(default=1, bounds=(1, 10))
    linestyle = bch.StringSweep(["solid", "dashed", "dotted"])
    color = bch.StringSweep(["red", "green", "blue"])
    start_angle = bch.FloatSweep(default=0, bounds=[0, 360])
    polygon = bch.ResultImage()
    polygon_small = bch.ResultImage()

    area = bch.ResultVar()
    side_length = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = polygon_points(self.radius, self.sides, self.start_angle)
        filepath = bch.gen_image_path("polygon")
        self.polygon = self.points_to_polygon_png(points, filepath, dpi=30)
        self.polygon_small = self.points_to_polygon_png(
            points, bch.gen_image_path("polygon"), dpi=10
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


def example_image_vid_sequential1(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = BenchPolygons().to_bench(run_cfg, report)
    res = bench.plot_sweep(input_vars=["sides"])

    bench.report.append(res.to_panes(zip_results=True))

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.cache_samples = True
    ex_run_cfg.overwrite_sample_cache = True
    ex_run_cfg.level = 3

    example_image_vid_sequential1(ex_run_cfg).report.show()
