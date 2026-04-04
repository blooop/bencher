"""Meta-generator: Container Tab Layout Showcase.

Generates examples demonstrating tab-based PaneLayout options using
the BenchPolygons class from example_image.py.  Only the non-default
layouts are shown (grid is already demonstrated by every other example).
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "container_tabs"

_BENCHABLE_MODULE = "bencher.example.example_image"
_BENCHABLE_CLASS = "BenchPolygons"

# Only generate examples for layouts that differ from the default grid.
_TAB_LAYOUTS = ["tabs", "tabs_and_grid"]


class MetaContainerTabLayout(MetaGeneratorBase):
    """Generate examples showing tab-based PaneLayout modes."""

    layout = bn.StringSweep(_TAB_LAYOUTS, doc="Pane layout mode")

    def benchmark(self):
        layout = self.layout
        function_name = f"example_container_tab_{layout}"
        filename = function_name
        title = f"Container Layout: PaneLayout.{layout}"

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


# --- Entry point -----------------------------------------------------------


def example_meta_container_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Generate container tab layout meta-examples."""
    bench = MetaContainerTabLayout().to_bench(run_cfg)
    bench.plot_sweep(
        title="Container Tab Layout Examples",
        input_vars=[bn.sweep("layout", _TAB_LAYOUTS)],
    )
    return bench


if __name__ == "__main__":
    bn.run(example_meta_container_tabs)
