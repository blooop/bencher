import bencher as bch
from bencher.example.example_composable_container_image import BenchComposableContainerImage


class BenchComposableContainerVideo(bch.ParametrizedSweep):
    unequal_length = bch.BoolSweep()
    compose_method = bch.EnumSweep(bch.ComposeType)
    labels = bch.BoolSweep()
    polygon_vid = bch.ResultVideo()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vr = bch.ComposableContainerVideo()
        for i in range(3, 5):
            num_frames = i * 10 if self.unequal_length else 5
            res = BenchComposableContainerImage().__call__(
                compose_method=bch.ComposeType.sequence, sides=i, num_frames=num_frames
            )
            vr.append(res["polygon_vid"])

        self.polygon_vid = vr.to_video(bch.RenderCfg(compose_method=kwargs.get("compose_method")))
        return self.get_results_values_as_dict()


def example_composable_container_video(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = BenchComposableContainerVideo().to_bench(run_cfg, report)

    bench.result_vars = ["polygon_vid"]
    bench.add_plot_callback(bch.BenchResult.to_panes)
    bench.add_plot_callback(bch.BenchResult.to_video_grid, result_types=(bch.ResultVideo))
    bench.add_plot_callback(bch.BenchResult.to_video_summary, result_types=(bch.ResultVideo))
    bench.plot_sweep(input_vars=["compose_method", "labels"], const_vars=dict(unequal_length=True))

    res = bench.plot_sweep(
        input_vars=[],
        const_vars=dict(unequal_length=False, compose_method=bch.ComposeType.sequence),
        plot_callbacks=False,
    )

    bench.report.append(res.to_video_grid())

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    example_composable_container_video(ex_run_cfg).report.show()
