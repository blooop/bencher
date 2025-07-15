import bencher as bch

from bencher.example.example_image import BenchPolygons


class BenchComposableContainerImage(BenchPolygons):
    compose_method = bch.EnumSweep(bch.ComposeType)
    labels = bch.BoolSweep()
    num_frames = bch.IntSweep(default=5, bounds=[1, 100])

    polygon_vid = bch.ResultVideo()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        var_name = None
        var_value = None

        if self.labels:
            var_name = "sides"
            var_value = self.sides
        vr = bch.ComposableContainerVideo()
        for i in range(self.num_frames):
            res = super().__call__(start_angle=i)
            print(res)
            vr.append(res["polygon"])
        self.polygon_vid = vr.to_video(
            bch.RenderCfg(
                compose_method=self.compose_method,
                var_name=var_name,
                var_value=var_value,
                max_frame_duration=1.0 / 20.0,
            )
        )
        return self.get_results_values_as_dict()


def example_composable_container_image(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    bench = BenchComposableContainerImage().to_bench(run_cfg, report)
    # bench.add_plot_callback(bch.BenchResult.to_panes)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, result_types=(bch.ResultVideo))
    # bench.add_plot_callback(bch.BenchResult.to_video_summary, result_types=(bch.ResultVideo))
    # bench.plot_sweep(input_vars=["compose_method", "labels"])

    bench.plot_sweep(input_vars=["compose_method"])

    # bench.compose_
    # bench.plot_sweep(
    # input_vars=[bch.p("num_frames", [2, 8, 20])],
    # const_vars=dict(compose_method=bch.ComposeType.sequence),
    # )

    return bench


if __name__ == "__main__":
    ex_run_cfg = bch.BenchRunCfg()
    ex_composable_image = example_composable_container_image(ex_run_cfg)
    ex_composable_image.report.show()
