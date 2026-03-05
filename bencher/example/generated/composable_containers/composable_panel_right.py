"""Auto-generated example: Composable Panel: ComposeType.right."""

import bencher as bch
from bencher.example.meta.benchable_objects import (
    BenchableImageResult,
    _polygon_points,
    _draw_polygon_image,
)


class _PanelComposeDemo(BenchableImageResult):
    """Compose polygon images into a Panel layout."""

    result_image = bch.ResultImage(doc="Composed panel image")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color, linewidth=3)
        filepath = bch.gen_image_path("panel_compose")
        img.save(filepath, "PNG")
        self.result_image = str(filepath)
        return self.get_results_values_as_dict()


def example_composable_panel_right(run_cfg=None):
    """Composable Panel: ComposeType.right."""
    bench = _PanelComposeDemo().to_bench(run_cfg)
    bench.plot_sweep(
        title="Panel Layout: ComposeType.right",
        input_vars=["sides", "color"],
        result_vars=["result_image"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_composable_panel_right, level=2)
