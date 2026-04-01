"""Example: Display multi-dimensional container results using tabs instead of grids.

Demonstrates PaneLayout options for controlling how dimensions are arranged:
- PaneLayout.grid: rows/columns for all dimensions (default)
- PaneLayout.tabs: tabs for all outer dimensions
- PaneLayout.tabs_and_grid: tabs for the outermost dimension, grid for inner ones

This is especially useful for large container results (e.g. rerun windows, images, videos)
where a single large display with tab selection is preferable to a dense grid.
"""

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


def _draw_polygon_image(points, color, linewidth=3, size=300):
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    scaled = [((p[0] + 1) * size / 2, (1 - p[1]) * size / 2) for p in points]
    draw.line(scaled, fill=color, width=int(linewidth))
    return img


class PolygonSweep(bn.ParametrizedSweep):
    sides = bn.IntSweep(default=3, bounds=(3, 7), doc="Number of polygon sides")
    color = bn.StringSweep(["red", "green", "blue"], doc="Line color")
    radius = bn.FloatSweep(default=0.6, bounds=(0.3, 1.0), doc="Polygon radius")

    polygon = bn.ResultImage(doc="Rendered polygon image")

    def benchmark(self):
        points = _polygon_points(self.radius, self.sides)
        img = _draw_polygon_image(points, self.color)
        filepath = bn.gen_image_path("tab_polygon")
        img.save(filepath, "PNG")
        self.polygon = str(filepath)


def example_container_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Show container results using tabs layout for dimension navigation."""

    bench = PolygonSweep().to_bench(run_cfg)

    # Grid layout (default) - all dimensions as rows/columns
    bench.plot_sweep(
        title="Grid Layout (default)",
        input_vars=["sides", "color"],
        result_vars=["polygon"],
    )

    # Tabs layout - outer dimensions as tabs
    bench.plot_sweep(
        title="Tabs Layout",
        input_vars=["sides", "color"],
        result_vars=["polygon"],
        run_cfg=bn.BenchRunCfg.with_defaults(run_cfg, pane_layout=bn.PaneLayout.tabs),
    )

    # Mixed layout - outermost dimension as tabs, inner as grid
    bench.plot_sweep(
        title="Tabs + Grid Layout (3 dims)",
        input_vars=["sides", "color", "radius"],
        result_vars=["polygon"],
        run_cfg=bn.BenchRunCfg.with_defaults(run_cfg, pane_layout=bn.PaneLayout.tabs_and_grid),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_container_tabs, level=2)
