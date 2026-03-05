"""Auto-generated example: ResultImage: Progressive Multi-Parameter Sweep."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_result_image_progressive(run_cfg=None):
    """ResultImage: Progressive Multi-Parameter Sweep."""
    bench = BenchableImageResult().to_bench(run_cfg)
    bench.add_plot_callback(bch.BenchResult.to_sweep_summary)
    bench.add_plot_callback(bch.BenchResult.to_panes, level=3)
    sweep_vars = ["sides", "radius", "color"]
    for i in range(1, len(sweep_vars) + 1):
        bench.plot_sweep(
            f"Polygons Sweeping {i} Parameter(s)",
            input_vars=sweep_vars[:i],
            result_vars=["polygon", "area"],
        )

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_progressive, level=3)
