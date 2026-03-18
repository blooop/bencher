"""Auto-generated example: ResultImage: Composable Container Video from Images."""

from typing import Any

import bencher as bch
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


class _ComposableImageDemo(bch.ParametrizedSweep):
    """Composable polygon renderer with video output."""

    sides = bch.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    radius = bch.FloatSweep(default=0.6, bounds=(0.2, 1.0), doc="Polygon radius")
    color = bch.StringSweep(["red", "green", "blue"], doc="Line color")
    compose_method = bch.EnumSweep(
        bch.ComposeType,
        default=bch.ComposeType.right,
        doc="Compose method",
    )
    num_frames = bch.IntSweep(default=5, bounds=[2, 20], doc="Frame count")
    polygon_vid = bch.ResultVideo()

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        vr = bch.ComposableContainerVideo()
        for i in range(self.num_frames):
            angle = 360.0 * i / self.num_frames
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bch.gen_image_path("composable")
            img.save(filepath, "PNG")
            vr.append(str(filepath))
        self.polygon_vid = vr.to_video(
            bch.RenderCfg(
                compose_method=self.compose_method,
                max_frame_duration=1.0 / 20.0,
            )
        )
        return self.get_results_values_as_dict()


def example_result_image_composable(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """ResultImage: Composable Container Video from Images."""
    bench = _ComposableImageDemo().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[
            bch.p(
                "compose_method",
                [bch.ComposeType.right, bch.ComposeType.sequence, bch.ComposeType.down],
            )
        ]
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_composable, level=2)
