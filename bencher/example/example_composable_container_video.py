import bencher as bn
from bencher.example.example_composable_container_image import BenchComposableContainerImage


class BenchComposableContainerVideo(bn.ParametrizedSweep):
    unequal_length = bn.BoolSweep()
    compose_method = bn.EnumSweep(bn.ComposeType)
    labels = bn.BoolSweep()
    polygon_vid = bn.ResultVideo()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        vr = bn.ComposableContainerVideo()
        for i in range(3, 5):
            num_frames = i * 10 if self.unequal_length else 5
            res = BenchComposableContainerImage().__call__(
                compose_method=bn.ComposeType.sequence, sides=i, num_frames=num_frames
            )
            vr.append(res["polygon_vid"])

        self.polygon_vid = vr.to_video(bn.RenderCfg(compose_method=kwargs.get("compose_method")))
        return self.get_results_values_as_dict()


def example_composable_container_video(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchComposableContainerVideo().to_bench(run_cfg)

    bench.result_vars = ["polygon_vid"]
    bench.add_plot_callback(bn.BenchResult.to_panes)
    bench.add_plot_callback(bn.BenchResult.to_video_grid, result_types=(bn.ResultVideo))
    bench.add_plot_callback(bn.BenchResult.to_video_summary, result_types=(bn.ResultVideo))
    bench.plot_sweep(input_vars=["compose_method", "labels"], const_vars=dict(unequal_length=True))

    res = bench.plot_sweep(
        input_vars=[],
        const_vars=dict(unequal_length=False, compose_method=bn.ComposeType.sequence),
        plot_callbacks=False,
    )

    bench.report.append(res.to_video_grid())

    return bench


if __name__ == "__main__":
    bn.run(example_composable_container_video)
