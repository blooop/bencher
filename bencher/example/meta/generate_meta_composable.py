"""Meta-generator: Composable Container Showcase.

Generates examples demonstrating the composable container system across all
three backends (Video, Panel, Dataset) and all four ComposeType strategies
(right, down, sequence, overlay).
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "composable_containers"

BENCHABLE_MODULE = "bencher.example.meta.benchable_objects"


class MetaComposableVideo(MetaGeneratorBase):
    """Generate examples showing ComposableContainerVideo with each ComposeType."""

    compose = bch.StringSweep(
        ["right", "down", "sequence", "overlay"],
        doc="Composition strategy",
    )

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        compose = self.compose
        filename = f"composable_video_{compose}"
        function_name = f"example_composable_video_{compose}"
        title = f"Composable Video: ComposeType.{compose}"

        imports = (
            "import bencher as bch\n"
            f"from {BENCHABLE_MODULE} import "
            "BenchableImageResult, _polygon_points, _draw_polygon_image\n"
            "\n\n"
            "class _VideoComposeDemo(BenchableImageResult):\n"
            '    """Compose polygon frames into a video using ComposableContainerVideo."""\n'
            "\n"
            "    num_frames = bch.IntSweep(default=6, bounds=[3, 12], "
            'doc="Number of frames")\n'
            "    composed_video = bch.ResultVideo(doc='Composed video output')\n"
            "\n"
            "    def __call__(self, **kwargs):\n"
            "        self.update_params_from_kwargs(**kwargs)\n"
            "        vid = bch.ComposableContainerVideo()\n"
            "        for i in range(self.num_frames):\n"
            "            angle = 360.0 * i / self.num_frames\n"
            "            points = _polygon_points(self.radius, self.sides, "
            "start_angle=angle)\n"
            "            img = _draw_polygon_image(points, self.color, linewidth=3)\n"
            '            filepath = bch.gen_image_path("compose_frame")\n'
            '            img.save(filepath, "PNG")\n'
            "            vid.append(str(filepath))\n"
            "        self.composed_video = vid.to_video(\n"
            "            bch.RenderCfg(\n"
            f"                compose_method=bch.ComposeType.{compose},\n"
            "                max_frame_duration=1.0 / 10.0,\n"
            "            )\n"
            "        )\n"
            "        return self.get_results_values_as_dict()"
        )
        body = (
            "bench = _VideoComposeDemo().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    input_vars=["sides"],\n'
            '    result_vars=["composed_video"],\n'
            ")\n"
        )

        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            run_kwargs={"level": 2},
        )

        return super().__call__()


class MetaComposablePanel(MetaGeneratorBase):
    """Generate examples showing ComposableContainerPanel with each ComposeType."""

    compose = bch.StringSweep(
        ["right", "down", "sequence"],
        doc="Composition strategy",
    )

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        compose = self.compose
        filename = f"composable_panel_{compose}"
        function_name = f"example_composable_panel_{compose}"
        title = f"Composable Panel: ComposeType.{compose}"

        imports = (
            "import bencher as bch\n"
            f"from {BENCHABLE_MODULE} import "
            "BenchableImageResult, _polygon_points, _draw_polygon_image\n"
            "\n\n"
            "class _PanelComposeDemo(BenchableImageResult):\n"
            '    """Compose polygon images into a Panel layout."""\n'
            "\n"
            "    result_image = bch.ResultImage(doc='Composed panel image')\n"
            "\n"
            "    def __call__(self, **kwargs):\n"
            "        self.update_params_from_kwargs(**kwargs)\n"
            "        points = _polygon_points(self.radius, self.sides)\n"
            "        img = _draw_polygon_image(points, self.color, linewidth=3)\n"
            '        filepath = bch.gen_image_path("panel_compose")\n'
            '        img.save(filepath, "PNG")\n'
            "        self.result_image = str(filepath)\n"
            "        return self.get_results_values_as_dict()"
        )
        body = (
            "bench = _PanelComposeDemo().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            f'    title="Panel Layout: ComposeType.{compose}",\n'
            '    input_vars=["sides", "color"],\n'
            '    result_vars=["result_image"],\n'
            ")\n"
        )

        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            run_kwargs={"level": 2},
        )

        return super().__call__()


class MetaComposableDataset(MetaGeneratorBase):
    """Generate examples showing ComposableContainerDataset with each ComposeType."""

    compose = bch.StringSweep(
        ["right", "down", "sequence", "overlay"],
        doc="Composition strategy",
    )

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        compose = self.compose
        filename = f"composable_dataset_{compose}"
        function_name = f"example_composable_dataset_{compose}"
        title = f"Composable Dataset: ComposeType.{compose}"

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class="BenchableDataSetResult",
            benchable_module=BENCHABLE_MODULE,
            input_vars='["value"]',
            result_vars='["result_ds"]',
            run_kwargs={"level": 3},
        )

        return super().__call__()


class MetaComposableAllTypes(MetaGeneratorBase):
    """Generate an example that sweeps ComposeType across the Video backend."""

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        imports = (
            "import bencher as bch\n"
            f"from {BENCHABLE_MODULE} import "
            "BenchableImageResult, _polygon_points, _draw_polygon_image\n"
            "\n\n"
            "class _ComposeTypeSweep(BenchableImageResult):\n"
            '    """Sweep all ComposeType values in a single benchmark."""\n'
            "\n"
            "    compose_method = bch.EnumSweep(\n"
            "        bch.ComposeType,\n"
            "        default=bch.ComposeType.right,\n"
            "        doc='Composition method',\n"
            "    )\n"
            "    composed_video = bch.ResultVideo(doc='Composed video output')\n"
            "\n"
            "    def __call__(self, **kwargs):\n"
            "        self.update_params_from_kwargs(**kwargs)\n"
            "        vid = bch.ComposableContainerVideo()\n"
            "        for i in range(5):\n"
            "            angle = 360.0 * i / 5\n"
            "            points = _polygon_points(self.radius, self.sides, "
            "start_angle=angle)\n"
            "            img = _draw_polygon_image(points, self.color, linewidth=3)\n"
            '            filepath = bch.gen_image_path("all_types")\n'
            '            img.save(filepath, "PNG")\n'
            "            vid.append(str(filepath))\n"
            "        self.composed_video = vid.to_video(\n"
            "            bch.RenderCfg(\n"
            "                compose_method=self.compose_method,\n"
            "                max_frame_duration=1.0 / 10.0,\n"
            "            )\n"
            "        )\n"
            "        return self.get_results_values_as_dict()"
        )
        body = (
            "bench = _ComposeTypeSweep().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Composable Container: All ComposeTypes",\n'
            "    input_vars=[\n"
            "        bch.p(\n"
            '            "compose_method",\n'
            "            [bch.ComposeType.right, bch.ComposeType.down,\n"
            "             bch.ComposeType.sequence, bch.ComposeType.overlay],\n"
            "        )\n"
            "    ],\n"
            '    result_vars=["composed_video"],\n'
            ")\n"
        )

        self.generate_example(
            title="Composable Container: All ComposeTypes Compared",
            output_dir=OUTPUT_DIR,
            filename="composable_all_compose_types",
            function_name="example_composable_all_compose_types",
            imports=imports,
            body=body,
            run_kwargs={"level": 2},
        )

        return super().__call__()


# --- Entry point -----------------------------------------------------------


def example_meta_composable(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Generate all composable container meta-examples."""
    # Video backend: one example per ComposeType
    bench = MetaComposableVideo().to_bench(run_cfg)
    bench.plot_sweep(
        title="Composable Video Examples",
        input_vars=[bch.p("compose", ["right", "down", "sequence", "overlay"])],
    )

    # Panel backend: one example per supported ComposeType
    bench2 = MetaComposablePanel().to_bench(run_cfg)
    bench2.plot_sweep(
        title="Composable Panel Examples",
        input_vars=[bch.p("compose", ["right", "down", "sequence"])],
    )

    # Dataset backend: one example per ComposeType
    bench3 = MetaComposableDataset().to_bench(run_cfg)
    bench3.plot_sweep(
        title="Composable Dataset Examples",
        input_vars=[bch.p("compose", ["right", "down", "sequence", "overlay"])],
    )

    # Sweep all ComposeTypes in a single benchmark
    all_types = MetaComposableAllTypes().to_bench(run_cfg)
    all_types.plot_sweep(title="All ComposeTypes Sweep")

    return bench


if __name__ == "__main__":
    bch.run(example_meta_composable)
