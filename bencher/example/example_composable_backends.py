"""Demonstrates all ComposeType strategies across composable container backends.

Shows how images can be composed using right, down, sequence, and overlay
composition strategies using both the Panel and Video backends.
"""

import numpy as np
from PIL import Image, ImageDraw

import bencher as bn


def _make_color_block(color: str, label: str, size: int = 80) -> str:
    """Create a small labeled color block image and return its file path."""
    colors = {"red": (220, 60, 60), "green": (60, 180, 60), "blue": (60, 60, 220)}
    rgb = colors.get(color, (128, 128, 128))
    img = Image.new("RGB", (size, size), rgb)
    draw = ImageDraw.Draw(img)
    draw.text((4, 4), label, fill=(255, 255, 255))
    path = bn.gen_image_path(f"block_{color}_{label}")
    img.save(path, "PNG")
    return str(path)


class ComposeDemo(bn.ParametrizedSweep):
    """Sweep over ComposeType to show all composition strategies."""

    compose = bn.EnumSweep(bn.ComposeType, doc="Composition method")
    color = bn.StringSweep(["red", "green", "blue"], doc="Block color")

    result_image = bn.ResultImage(doc="Composed image output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        imgs = [_make_color_block(self.color, f"{i}") for i in range(3)]

        vid = bn.ComposableContainerVideo()
        for img_path in imgs:
            vid.append(img_path)

        render_cfg = bn.RenderCfg(
            compose_method=self.compose,
            duration=2.0,
            duration_target=False,
        )
        clip = vid.render(render_cfg)
        frame = clip.get_frame(0)
        frame_img = Image.fromarray(np.uint8(frame))
        out_path = bn.gen_image_path("composed")
        frame_img.save(out_path, "PNG")
        self.result_image = str(out_path)
        return super().__call__()


def example_composable_backends(run_cfg: bn.BenchRunCfg = None, report: bn.BenchReport = None):
    bench = ComposeDemo().to_bench(run_cfg, report)
    bench.plot_sweep(
        title="Composable Container Backends",
        input_vars=["compose"],
        result_vars=["result_image"],
    )
    return bench


if __name__ == "__main__":
    bn.run(example_composable_backends, level=2)
