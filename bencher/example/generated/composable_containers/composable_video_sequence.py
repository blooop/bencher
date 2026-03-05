"""Auto-generated example: Composable Video: ComposeType.sequence."""

import bencher as bch
from bencher.example.meta.benchable_objects import (
    BenchableImageResult,
    _polygon_points,
    _draw_polygon_image,
)


class _VideoComposeDemo(BenchableImageResult):
    """Compose polygon frames into a video using ComposableContainerVideo."""

    num_frames = bch.IntSweep(default=6, bounds=[3, 12], doc="Number of frames")
    composed_video = bch.ResultVideo(doc="Composed video output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vid = bch.ComposableContainerVideo()
        for i in range(self.num_frames):
            angle = 360.0 * i / self.num_frames
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bch.gen_image_path("compose_frame")
            img.save(filepath, "PNG")
            vid.append(str(filepath))
        self.composed_video = vid.to_video(
            bch.RenderCfg(
                compose_method=bch.ComposeType.sequence,
                max_frame_duration=1.0 / 10.0,
            )
        )
        return self.get_results_values_as_dict()


def example_composable_video_sequence(run_cfg=None):
    """Composable Video: ComposeType.sequence."""
    bench = _VideoComposeDemo().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["sides"],
        result_vars=["composed_video"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_composable_video_sequence, level=2)
