"""Auto-generated example: ResultVideo: Aggregate with Mixed Video and Image."""

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


class PolygonAnimator(bn.ParametrizedSweep):
    """Renders rotating polygon animations."""

    sides = bn.IntSweep(default=4, bounds=(3, 7), doc="Number of polygon sides")
    speed = bn.FloatSweep(default=1.0, bounds=(0.5, 3.0), doc="Rotation speed multiplier")
    animation = bn.ResultVideo(doc="Rotating polygon video")
    frame_snapshot = bn.ResultImage(doc="Last frame snapshot")
    max_angle = bn.ResultFloat(units="deg", doc="Maximum rotation angle in the animation")

    def benchmark(self):
        vid_writer = bn.VideoWriter()
        num_frames = 8
        for i in range(num_frames):
            angle = self.speed * (360.0 * i / num_frames)
            points = _polygon_points(0.7, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, "white", linewidth=3, size=200)
            vid_writer.append(np.array(img.convert("RGB")))
        self.animation = vid_writer.write()
        self.frame_snapshot = bn.VideoWriter.extract_frame(self.animation)
        self.max_angle = self.speed * 360.0 * (num_frames - 1) / num_frames


def example_result_video_aggregate(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """ResultVideo: Aggregate with Mixed Video and Image."""
    bench = PolygonAnimator().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["sides", "speed"],
        result_vars=["animation", "frame_snapshot", "max_angle"],
        description="aggregate=True collapses the speed dimension. Videos and images "
        "should only appear once in the non-aggregated view, not duplicated "
        "in the aggregated view.",
        aggregate=True,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_result_video_aggregate, level=2)
