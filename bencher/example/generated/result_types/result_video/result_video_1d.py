"""Auto-generated example: Result Video: 1D input."""

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


class PolygonAnimator(bch.ParametrizedSweep):
    """Renders rotating polygon animations."""

    sides = bch.IntSweep(default=4, bounds=(3, 7), doc="Number of polygon sides")
    speed = bch.FloatSweep(default=1.0, bounds=(0.5, 3.0), doc="Rotation speed multiplier")
    animation = bch.ResultVideo(doc="Rotating polygon video")
    frame_snapshot = bch.ResultImage(doc="Last frame snapshot")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        vid_writer = bch.VideoWriter()
        num_frames = 8
        for i in range(num_frames):
            angle = self.speed * (360.0 * i / num_frames)
            points = _polygon_points(0.7, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, "white", linewidth=3, size=200)
            vid_writer.append(np.array(img.convert("RGB")))
        self.animation = vid_writer.write()
        self.frame_snapshot = bch.VideoWriter.extract_frame(self.animation)
        return super().__call__()


def example_result_video_1d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Video: 1D input."""
    bench = PolygonAnimator().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["sides"], result_vars=["animation"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_video_1d, level=3)
