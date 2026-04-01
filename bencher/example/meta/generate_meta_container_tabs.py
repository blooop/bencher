"""Meta-generator: Container Tab Layout Showcase.

Generates examples demonstrating the PaneLayout options for controlling how
multi-dimensional data is laid out in panel displays — grids, tabs, or a
combination of both.  Uses the BenchPolygons class from example_image.py.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "container_tabs"

_BENCHABLE_MODULE = "bencher.example.example_image"
_BENCHABLE_CLASS = "BenchPolygons"


class MetaContainerTabLayout(MetaGeneratorBase):
    """Generate examples showing each PaneLayout with 2 input dimensions."""

    layout = bn.StringSweep(
        ["grid", "tabs", "tabs_and_grid"],
        doc="Pane layout mode",
    )

    def benchmark(self):
        layout = self.layout
        filename = f"container_tab_layout_{layout}"
        function_name = f"example_container_tab_layout_{layout}"
        title = f"Container Layout: PaneLayout.{layout} (2D)"

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=_BENCHABLE_CLASS,
            benchable_module=_BENCHABLE_MODULE,
            input_vars='["sides", "color"]',
            result_vars='["polygon"]',
            run_cfg_lines=[
                f"run_cfg.pane_layout = bn.PaneLayout.{layout}",
            ],
            run_kwargs={"level": 2},
        )


class MetaContainerTabLayout3D(MetaGeneratorBase):
    """Generate examples showing each PaneLayout with 3 input dimensions."""

    layout = bn.StringSweep(
        ["grid", "tabs", "tabs_and_grid"],
        doc="Pane layout mode",
    )

    def benchmark(self):
        layout = self.layout
        filename = f"container_tab_3d_{layout}"
        function_name = f"example_container_tab_3d_{layout}"
        title = f"Container Layout: PaneLayout.{layout} (3D)"

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=_BENCHABLE_CLASS,
            benchable_module=_BENCHABLE_MODULE,
            input_vars='["sides", "color", "radius"]',
            result_vars='["polygon"]',
            run_cfg_lines=[
                f"run_cfg.pane_layout = bn.PaneLayout.{layout}",
            ],
            run_kwargs={"level": 2},
        )


# --- Entry point -----------------------------------------------------------


def example_meta_container_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Generate all container tab layout meta-examples."""
    # 2D layout examples: one per PaneLayout
    bench = MetaContainerTabLayout().to_bench(run_cfg)
    bench.plot_sweep(
        title="Container Tab Layout Examples (2D)",
        input_vars=[bn.sweep("layout", ["grid", "tabs", "tabs_and_grid"])],
    )

    # 3D layout examples: one per PaneLayout
    bench3d = MetaContainerTabLayout3D().to_bench(run_cfg)
    bench3d.plot_sweep(
        title="Container Tab Layout Examples (3D)",
        input_vars=[bn.sweep("layout", ["grid", "tabs", "tabs_and_grid"])],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_container_tabs)
