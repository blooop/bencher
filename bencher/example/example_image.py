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
    color = bch.StringSweep(["red", "green", "blue"])
    start_angle = bch.FloatSweep(default=0, bounds=[0, 360])
    polygon = bch.ResultImage()
    area = bch.ResultVar()
    side_length = bch.ResultVar()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = polygon_points(self.radius, self.sides, self.start_angle)
        filepath = bch.gen_image_path("polygon")
        self.polygon = self.points_to_polygon_png(points, filepath)
        # Verify filepath is being returned
        assert isinstance(self.polygon, str), f"Expected string filepath, got {type(self.polygon)}"

        self.side_length = 2 * self.radius * math.sin(math.pi / self.sides)
        self.area = (self.sides * self.side_length**2) / (4 * math.tan(math.pi / self.sides))
        return super().__call__()

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


def example_image(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    run_cfg.cache_results = False
    bench = bch.Bench("polygons", BenchPolygons(), run_cfg=run_cfg, report=report)

    bench.result_vars = ["polygon", "area"]

    bench.add_plot_callback(bch.BenchResult.to_sweep_summary)
    # bench.add_plot_callback(bch.BenchResult.to_auto, level=2)
    bench.add_plot_callback(bch.BenchResult.to_panes, level=3)
    # bench.add_plot_callback(bch.BenchResult.to_panes)

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


def example_image_vid(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    bench = BenchPolygons().to_bench(run_cfg, report)
    bench.add_plot_callback(bch.BenchResult.to_sweep_summary)
    bench.add_plot_callback(
        bch.BenchResult.to_video_grid,
        target_duration=0.06,
        compose_method_list=[
            bch.ComposeType.right,
            bch.ComposeType.right,
            bch.ComposeType.sequence,
        ],
    )
    # from functools import partial
    # bench.add_plot_callback(bch.BenchResult.to_video_summary)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=0)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=2)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=3)

    bench.plot_sweep(input_vars=["radius"])
    # res = bench.plot_sweep(input_vars=["radius"], plot=False)
    # bench.report.append(res.to_video_grid(target_duration=0.06))
    bench.plot_sweep(input_vars=["radius", "sides"])
    # bench.plot_sweep(input_vars=["radius", "sides", "linewidth"])
    # bench.plot_sweep(input_vars=["radius", "sides", "linewidth", "color"])

    return bench


if __name__ == "__main__":

    def simple():
        bench = BenchPolygons().to_bench(bch.BenchRunCfg(level=4))

        # bench.plot_sweep(input_vars=["sides","color","radius"])

        # res = bench.sweep(input_vars=["sides", "radius"])

        bench.plot_sweep(input_vars=["sides"])
        bench.plot_sweep(input_vars=["sides", "color"])

        res = bench.plot_sweep(input_vars=["sides", "radius"])
        bench.report.append(res.to_heatmap(target_dimension=3))
        bench.report.append(res.to_line(target_dimension=1))

        return bench

    def example_image_vid_sequential(
        run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
    ) -> bch.Bench:
        bench = BenchPolygons().to_bench(run_cfg, report)
        bench.add_plot_callback(bch.BenchResult.to_title)
        bench.add_plot_callback(bch.BenchResult.to_video_grid)
        bench.sweep_sequential(input_vars=["radius", "sides", "linewidth", "color"], group_size=4)
        return bench

    # def example_image_pairs()

    ex_run_cfg = bch.BenchRunCfg()
    ex_run_cfg.cache_samples = True
    # ex_run_cfg.debug = True
    # ex_run_cfg.repeats = 2
    ex_run_cfg.level = 4
    # example_image_vid(ex_run_cfg).report.show()
    simple().report.show()

    # example_image_vid_sequential(ex_run_cfg).report.show()
    # example_image(ex_run_cfg).report.show()
