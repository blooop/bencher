"""Example: Display multi-dimensional container results using tabs instead of grids.

Demonstrates PaneLayout options for controlling how dimensions are arranged:
- PaneLayout.grid: rows/columns for all dimensions (default)
- PaneLayout.tabs: tabs for all outer dimensions
- PaneLayout.tabs_and_grid: tabs for the outermost dimension, grid for inner ones

This is especially useful for large container results (e.g. rerun windows, images, videos)
where a single large display with tab selection is preferable to a dense grid.
"""

import bencher as bn
from bencher.example.example_image import BenchPolygons


def example_container_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Show container results using tabs layout for dimension navigation."""

    bench = BenchPolygons().to_bench(run_cfg)

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
