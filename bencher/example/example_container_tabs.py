"""Example: Display multi-dimensional container results using tabs instead of grids.

Demonstrates PaneLayout options for controlling how dimensions are arranged:
- PaneLayout.grid: rows/columns for all dimensions (default)
- PaneLayout.tabs: tabs for all outer dimensions
- PaneLayout.tabs_and_grid: tabs for the outermost dimension, grid for inner ones
"""

import bencher as bn
from bencher.example.example_image import BenchPolygons


def example_container_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Show container results using tabs layout for dimension navigation."""

    bench = BenchPolygons().to_bench(run_cfg)

    bench.plot_sweep(
        title="Tabs Layout",
        input_vars=["sides", "color"],
        result_vars=["polygon"],
        run_cfg=bn.BenchRunCfg.with_defaults(run_cfg, pane_layout=bn.PaneLayout.tabs),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_container_tabs, level=2)
