"""Auto-generated example: ResultImage: Composable Container Video from Images."""

import bencher as bch
from bencher.example.meta.benchable_objects import BenchableImageResult
from bencher.example.meta.benchable_objects import _polygon_points, _draw_polygon_image


class _ComposableImageDemo(BenchableImageResult):
    compose_method = bch.EnumSweep(
        bch.ComposeType,
        default=bch.ComposeType.right,
        doc="Compose method",
    )
    num_frames = bch.IntSweep(default=5, bounds=[2, 20], doc="Frame count")
    polygon_vid = bch.ResultVideo()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vr = bch.ComposableContainerVideo()
        for i in range(self.num_frames):
            angle = 360.0 * i / self.num_frames
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bch.gen_image_path("composable")
            img.save(filepath, "PNG")
            vr.append(str(filepath))
        self.polygon_vid = vr.to_video(
            bch.RenderCfg(
                compose_method=self.compose_method,
                max_frame_duration=1.0 / 20.0,
            )
        )
        return self.get_results_values_as_dict()


def example_result_image_composable(run_cfg=None):
    """ResultImage: Composable Container Video from Images."""
    bench = _ComposableImageDemo().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=[
            bch.p(
                "compose_method",
                [bch.ComposeType.right, bch.ComposeType.sequence, bch.ComposeType.down],
            )
        ]
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_image_composable, level=2)
