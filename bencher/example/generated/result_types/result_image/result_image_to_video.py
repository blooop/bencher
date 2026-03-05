"""Auto-generated example: ResultImage: Image Sweep to Video Grid."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult


def example_result_image_to_video(run_cfg=None):
    """ResultImage: Image Sweep to Video Grid."""
    bench = BenchableImageResult().to_bench(run_cfg)
    bench.add_plot_callback(bch.BenchResult.to_sweep_summary)
    bench.add_plot_callback(
        bch.BenchResult.to_video_grid,
        target_duration=0.06,
        compose_method_list=[
            bch.ComposeType.right,
            bch.ComposeType.right,
            bch.ComposeType.sequence,
        ],
    )
    bench.plot_sweep(input_vars=["sides"])
    bench.plot_sweep(input_vars=["sides", "radius"])

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_to_video, level=3)
