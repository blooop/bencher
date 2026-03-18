"""Auto-generated example: Composable Video: ComposeType.down."""

from typing import Any

import math
import numpy as np
from PIL import Image, ImageDraw
import bencher as bch


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


class BenchableImageResult(bch.ParametrizedSweep):
    """Lightweight polygon renderer for composable container demos."""

    sides = bch.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    radius = bch.FloatSweep(default=0.6, bounds=(0.2, 1.0), doc="Polygon radius")
    color = bch.StringSweep(["red", "green", "blue"], doc="Line color")

    polygon = bch.ResultImage(doc="Rendered polygon image")
    area = bch.ResultVar("u^2", doc="Polygon area")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color, linewidth=3)
        filepath = bch.gen_image_path("polygon")
        img.save(filepath, "PNG")
        self.polygon = str(filepath)
        self.area = (self.sides * (2 * self.radius * math.sin(math.pi / self.sides)) ** 2) / (
            4 * math.tan(math.pi / self.sides)
        )
        return super().__call__()


class _VideoComposeDemo(BenchableImageResult):
    """Compose polygon frames into a video using ComposableContainerVideo."""

    num_frames = bch.IntSweep(default=6, bounds=[3, 12], doc="Number of frames")
    composed_video = bch.ResultVideo(doc="Composed video output")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        vid = bch.ComposableContainerVideo()
        for i in range(self.num_frames):
            angle = 360.0 * i / self.num_frames
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bch.gen_image_path("compose_frame")
            img.save(filepath, "PNG")
            vid.append(str(filepath))
        self.composed_video = vid.to_video(
            bch.RenderCfg(
                compose_method=bch.ComposeType.down,
                max_frame_duration=1.0 / 10.0,
            )
        )
        return self.get_results_values_as_dict()


def example_composable_video_down(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Composable Video: ComposeType.down."""
    bench = _VideoComposeDemo().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["sides"],
        result_vars=["composed_video"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_composable_video_down, level=2)
