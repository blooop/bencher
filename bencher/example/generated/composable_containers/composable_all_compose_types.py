"""Auto-generated example: Composable Container: All ComposeTypes Compared."""

import bencher as bch
from bencher.example.meta.benchable_objects import (
    BenchableImageResult,
    _polygon_points,
    _draw_polygon_image,
)


class _ComposeTypeSweep(BenchableImageResult):
    """Sweep all ComposeType values in a single benchmark."""

    compose_method = bch.EnumSweep(
        bch.ComposeType,
        default=bch.ComposeType.right,
        doc="Composition method",
    )
    composed_video = bch.ResultVideo(doc="Composed video output")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vid = bch.ComposableContainerVideo()
        for i in range(5):
            angle = 360.0 * i / 5
            points = _polygon_points(self.radius, self.sides, start_angle=angle)
            img = _draw_polygon_image(points, self.color, linewidth=3)
            filepath = bch.gen_image_path("all_types")
            img.save(filepath, "PNG")
            vid.append(str(filepath))
        self.composed_video = vid.to_video(
            bch.RenderCfg(
                compose_method=self.compose_method,
                max_frame_duration=1.0 / 10.0,
            )
        )
        return self.get_results_values_as_dict()


def example_composable_all_compose_types(run_cfg=None):
    """Composable Container: All ComposeTypes Compared."""
    bench = _ComposeTypeSweep().to_bench(run_cfg)
    bench.plot_sweep(
        title="Composable Container: All ComposeTypes",
        input_vars=[
            bch.p(
                "compose_method",
                [
                    bch.ComposeType.right,
                    bch.ComposeType.down,
                    bch.ComposeType.sequence,
                    bch.ComposeType.overlay,
                ],
            )
        ],
        result_vars=["composed_video"],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_composable_all_compose_types, level=2)
