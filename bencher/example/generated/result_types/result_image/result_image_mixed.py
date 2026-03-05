"""Auto-generated example: ResultImage: Mixed Image and Scalar Results."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_result_image_mixed(run_cfg=None):
    """ResultImage: Mixed Image and Scalar Results."""
    bench = BenchableImageResult().to_bench(run_cfg)
    res = bench.plot_sweep(
        input_vars=["sides"],
        result_vars=["polygon", "area"],
    )
    bench.report.append(res.to_panes(zip_results=True))

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_mixed, level=3)
