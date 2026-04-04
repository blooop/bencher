"""Auto-generated example: Container Layout: PaneLayout.tabs."""

import bencher as bn
from bencher.example.example_image import BenchPolygons


def example_container_tab_tabs(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Container Layout: PaneLayout.tabs."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()
    run_cfg.pane_layout = bn.PaneLayout.tabs
    bench = BenchPolygons().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["sides", "color"], result_vars=["polygon"])

    return bench


if __name__ == "__main__":
    bn.run(example_container_tab_tabs, level=2)
