"""Meta-generator: ResultImage and ResultVideo Showcase.

Generates examples demonstrating image and video result types, including
simple sweeps and rich feature demonstrations (progressive sweeps, mixed
results, video grids, composable containers).
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "result_types"

# --- Shared helper / class code snippets ------------------------------------

_POLYGON_HELPERS = """\
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
    return img"""

_IMAGE_CLASS_CODE = (
    _POLYGON_HELPERS
    + """


class PolygonRenderer(bch.ParametrizedSweep):
    \"\"\"Renders polygon images with configurable sides, radius, and color.\"\"\"
    sides = bch.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    radius = bch.FloatSweep(default=0.6, bounds=(0.2, 1.0), doc="Polygon radius")
    color = bch.StringSweep(["red", "green", "blue"], doc="Line color")
    polygon = bch.ResultImage(doc="Rendered polygon image")
    area = bch.ResultVar("u^2", doc="Polygon area")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color, linewidth=3)
        filepath = bch.gen_image_path("polygon")
        img.save(filepath, "PNG")
        self.polygon = str(filepath)
        self.area = (self.sides * (2 * self.radius * math.sin(math.pi / self.sides)) ** 2) / (4 * math.tan(math.pi / self.sides))
        return super().__call__()"""
)

_VIDEO_CLASS_CODE = (
    _POLYGON_HELPERS
    + """


class PolygonAnimator(bch.ParametrizedSweep):
    \"\"\"Renders rotating polygon animations.\"\"\"
    sides = bch.IntSweep(default=4, bounds=(3, 7), doc="Number of polygon sides")
    speed = bch.FloatSweep(default=1.0, bounds=(0.5, 3.0), doc="Rotation speed multiplier")
    animation = bch.ResultVideo(doc="Rotating polygon video")
    frame_snapshot = bch.ResultImage(doc="Last frame snapshot")

    def __call__(self, **kwargs):
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
        return super().__call__()"""
)

_EXTRA_IMPORTS = ["import math", "import numpy as np", "from PIL import Image, ImageDraw"]

# --- Simple sweep examples -------------------------------------------------

IMAGE_SWEEP_COMBOS = {
    0: {"input_vars": '["color"]', "dims_label": "0D"},
    1: {"input_vars": '["sides"]', "dims_label": "1D"},
    2: {"input_vars": '["sides", "radius"]', "dims_label": "2D"},
}

VIDEO_SWEEP_COMBOS = {
    0: {"input_vars": '["speed"]', "dims_label": "0D"},
    1: {"input_vars": '["sides"]', "dims_label": "1D"},
    2: {"input_vars": '["sides", "speed"]', "dims_label": "2D"},
}


class MetaImageVideoSweeps(MetaGeneratorBase):
    """Generate simple sweep examples for ResultImage and ResultVideo."""

    result_kind = bch.StringSweep(["result_image", "result_video"], doc="Image or video")
    input_dims = bch.IntSweep(default=0, bounds=(0, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        combos = IMAGE_SWEEP_COMBOS if self.result_kind == "result_image" else VIDEO_SWEEP_COMBOS
        if self.input_dims not in combos:
            return super().__call__()

        info = combos[self.input_dims]
        if self.result_kind == "result_image":
            benchable_class = "PolygonRenderer"
            result_vars = '["polygon"]'
            class_code = _IMAGE_CLASS_CODE
        else:
            benchable_class = "PolygonAnimator"
            result_vars = '["animation"]'
            class_code = _VIDEO_CLASS_CODE

        sub_dir = f"{OUTPUT_DIR}/{self.result_kind}"
        filename = f"{self.result_kind}_{self.input_dims}d"
        function_name = f"example_{self.result_kind}_{self.input_dims}d"
        title = f"{self.result_kind.replace('_', ' ').title()}: {info['dims_label']} input"

        level = 2 if self.input_dims >= 2 else 3

        self.generate_sweep_example(
            title=title,
            output_dir=sub_dir,
            filename=filename,
            function_name=function_name,
            benchable_class=benchable_class,
            benchable_module=None,
            input_vars=info["input_vars"],
            result_vars=result_vars,
            class_code=class_code,
            extra_imports=_EXTRA_IMPORTS,
            run_kwargs={"level": level},
        )

        return super().__call__()


# --- Rich examples ---------------------------------------------------------


class MetaImageVideoRich(MetaGeneratorBase):
    """Generate rich feature-demonstration examples for image/video results."""

    example_name = bch.StringSweep(
        [
            "result_image_progressive",
            "result_image_mixed",
            "result_image_to_video",
            "result_image_composable",
        ],
        doc="Rich example to generate",
    )

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        name = self.example_name
        generator = {
            "result_image_progressive": self._gen_progressive,
            "result_image_mixed": self._gen_mixed,
            "result_image_to_video": self._gen_to_video,
            "result_image_composable": self._gen_composable,
        }[name]
        generator()
        return super().__call__()

    # -- Progressive sweep (1 -> 2 -> 3 parameters) ---------------------------

    def _gen_progressive(self):
        imports = "\n".join(["import bencher as bch"] + _EXTRA_IMPORTS)
        body = (
            "bench = PolygonRenderer().to_bench(run_cfg)\n"
            "bench.add_plot_callback(bch.BenchResult.to_sweep_summary)\n"
            "bench.add_plot_callback(bch.BenchResult.to_panes, level=3)\n"
            'sweep_vars = ["sides", "radius", "color"]\n'
            "for i in range(1, len(sweep_vars) + 1):\n"
            "    bench.plot_sweep(\n"
            '        f"Polygons Sweeping {i} Parameter(s)",\n'
            "        input_vars=sweep_vars[:i],\n"
            '        result_vars=["polygon", "area"],\n'
            "    )\n"
        )
        self.generate_example(
            title="ResultImage: Progressive Multi-Parameter Sweep",
            output_dir=f"{OUTPUT_DIR}/result_image",
            filename="result_image_progressive",
            function_name="example_result_image_progressive",
            imports=imports,
            body=body,
            class_code=_IMAGE_CLASS_CODE,
            run_kwargs={"level": 3},
        )

    # -- Mixed image + scalar results ----------------------------------------

    def _gen_mixed(self):
        imports = "\n".join(["import bencher as bch"] + _EXTRA_IMPORTS)
        body = (
            "bench = PolygonRenderer().to_bench(run_cfg)\n"
            "res = bench.plot_sweep(\n"
            '    input_vars=["sides"],\n'
            '    result_vars=["polygon", "area"],\n'
            ")\n"
            "bench.report.append(res.to_panes(zip_results=True))\n"
        )
        self.generate_example(
            title="ResultImage: Mixed Image and Scalar Results",
            output_dir=f"{OUTPUT_DIR}/result_image",
            filename="result_image_mixed",
            function_name="example_result_image_mixed",
            imports=imports,
            body=body,
            class_code=_IMAGE_CLASS_CODE,
            run_kwargs={"level": 3},
        )

    # -- Image sweep to video grid -------------------------------------------

    def _gen_to_video(self):
        imports = "\n".join(["import bencher as bch"] + _EXTRA_IMPORTS)
        body = (
            "bench = PolygonRenderer().to_bench(run_cfg)\n"
            "bench.add_plot_callback(bch.BenchResult.to_sweep_summary)\n"
            "bench.add_plot_callback(\n"
            "    bch.BenchResult.to_video_grid,\n"
            "    target_duration=0.06,\n"
            "    compose_method_list=[\n"
            "        bch.ComposeType.right,\n"
            "        bch.ComposeType.right,\n"
            "        bch.ComposeType.sequence,\n"
            "    ],\n"
            ")\n"
            'bench.plot_sweep(input_vars=["sides"])\n'
            'bench.plot_sweep(input_vars=["sides", "radius"])\n'
        )
        self.generate_example(
            title="ResultImage: Image Sweep to Video Grid",
            output_dir=f"{OUTPUT_DIR}/result_image",
            filename="result_image_to_video",
            function_name="example_result_image_to_video",
            imports=imports,
            body=body,
            class_code=_IMAGE_CLASS_CODE,
            run_kwargs={"level": 3},
        )

    # -- Composable container video from images ------------------------------

    def _gen_composable(self):
        composable_class_code = (
            _POLYGON_HELPERS + "\n\n\n"
            "class _ComposableImageDemo(bch.ParametrizedSweep):\n"
            '    """Composable polygon renderer with video output."""\n'
            '    sides = bch.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")\n'
            "    radius = bch.FloatSweep(default=0.6, bounds=(0.2, 1.0), "
            'doc="Polygon radius")\n'
            '    color = bch.StringSweep(["red", "green", "blue"], doc="Line color")\n'
            "    compose_method = bch.EnumSweep(\n"
            "        bch.ComposeType,\n"
            "        default=bch.ComposeType.right,\n"
            "        doc='Compose method',\n"
            "    )\n"
            '    num_frames = bch.IntSweep(default=5, bounds=[2, 20], doc="Frame count")\n'
            "    polygon_vid = bch.ResultVideo()\n"
            "\n"
            "    def __call__(self, **kwargs):\n"
            "        self.update_params_from_kwargs(**kwargs)\n"
            "        vr = bch.ComposableContainerVideo()\n"
            "        for i in range(self.num_frames):\n"
            "            angle = 360.0 * i / self.num_frames\n"
            "            points = _polygon_points(self.radius, self.sides, "
            "start_angle=angle)\n"
            "            img = _draw_polygon_image(points, self.color, linewidth=3)\n"
            '            filepath = bch.gen_image_path("composable")\n'
            '            img.save(filepath, "PNG")\n'
            "            vr.append(str(filepath))\n"
            "        self.polygon_vid = vr.to_video(\n"
            "            bch.RenderCfg(\n"
            "                compose_method=self.compose_method,\n"
            "                max_frame_duration=1.0 / 20.0,\n"
            "            )\n"
            "        )\n"
            "        return self.get_results_values_as_dict()"
        )

        imports = "\n".join(["import bencher as bch"] + _EXTRA_IMPORTS)
        body = (
            "bench = _ComposableImageDemo().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            "    input_vars=[\n"
            "        bch.p(\n"
            '            "compose_method",\n'
            "            [bch.ComposeType.right, bch.ComposeType.sequence, "
            "bch.ComposeType.down],\n"
            "        )\n"
            "    ]\n"
            ")\n"
        )
        self.generate_example(
            title="ResultImage: Composable Container Video from Images",
            output_dir=f"{OUTPUT_DIR}/result_image",
            filename="result_image_composable",
            function_name="example_result_image_composable",
            imports=imports,
            body=body,
            class_code=composable_class_code,
            run_kwargs={"level": 2},
        )


# --- Entry point -----------------------------------------------------------


def example_meta_image_video(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Generate all image/video meta-examples."""
    # Simple sweep examples
    bench = MetaImageVideoSweeps().to_bench(run_cfg)
    bench.plot_sweep(
        title="Image/Video Sweeps",
        input_vars=[
            bch.p("result_kind", ["result_image", "result_video"]),
            bch.p("input_dims", [0, 1, 2]),
        ],
    )

    # Rich feature examples
    bench2 = MetaImageVideoRich().to_bench(run_cfg)
    bench2.plot_sweep(
        title="Image/Video Rich Examples",
        input_vars=[
            bch.p(
                "example_name",
                [
                    "result_image_progressive",
                    "result_image_mixed",
                    "result_image_to_video",
                    "result_image_composable",
                ],
            ),
        ],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_image_video)
