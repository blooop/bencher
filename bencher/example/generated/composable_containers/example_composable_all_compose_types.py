"""Auto-generated example: Composable Container: All ComposeTypes Compared."""

import math
import numpy as np
from PIL import Image, ImageDraw
import bencher as bn


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


class BenchableImageResult(bn.ParametrizedSweep):
    """Lightweight polygon renderer for composable container demos."""

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


class _ComposeTypeSweep(BenchableImageResult):
    """Sweep all ComposeType values in a single benchmark."""

    compose_method = bn.EnumSweep(
        bn.ComposeType,
        default=bn.ComposeType.right,
        doc="Composition method",
    )
    composed_video = bn.ResultVideo(doc="Composed video output")

    def benchmark(self):
        vid = bn.ComposableContainerVideo()
        for i in range(5):
            angle = 360.0 * i / 5
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bn.gen_image_path("all_types")
            img.save(filepath, "PNG")
            vid.append(str(filepath))
        self.composed_video = vid.to_video(
            bn.RenderCfg(
                compose_method=self.compose_method,
                max_frame_duration=1.0 / 10.0,
            )
        )
        return self.get_results_values_as_dict()


def example_composable_all_compose_types(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Composable Container: All ComposeTypes Compared."""
    bench = _ComposeTypeSweep().to_bench(run_cfg)
    bench.plot_sweep(
        title="Composable Container: All ComposeTypes",
        input_vars=[
            bn.sweep(
                "compose_method",
                [
                    bn.ComposeType.right,
                    bn.ComposeType.down,
                    bn.ComposeType.sequence,
                    bn.ComposeType.overlay,
                ],
            )
        ],
        result_vars=["composed_video"],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_composable_all_compose_types, level=2)
