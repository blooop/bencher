import bencher as bch
from PIL import Image, ImageDraw
from bencher.video_writer import VideoWriter


class BenchImageTest(bch.ParametrizedSweep):
    character = bch.StringSweep(["a", "b", "c", "d", "e", "f"])
    r = bch.IntSweep(default=255, bounds=[0, 255])
    g = bch.IntSweep(default=255, bounds=[0, 255])
    b = bch.IntSweep(default=255, bounds=[0, 255])
    width = bch.IntSweep(default=100, bounds=[10, 100])
    height = bch.IntSweep(default=100, bounds=[10, 100])

    image = bch.ResultImage()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)

        img = Image.new("RGB", (self.width, self.height), color=(self.r, self.g, self.b))
        ImageDraw.Draw(img).text(
            (self.width / 2.0, self.height / 2.0),
            self.character,
            (0, 0, 0),
            anchor="mm",
            font_size=self.height,
        )
        self.image = bch.gen_image_path()
        img.save(self.image)
        return super().__call__(**kwargs)


def bench_image(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchImageTest().to_bench(run_cfg)
    bench.sweep_sequential(group_size=1)
    return bench


class BenchComposableContainerImage(BenchImageTest):
    compose_method = bch.EnumSweep(bch.ComposeType)
    labels = bch.BoolSweep()
    # num_frames = bch.IntSweep(default=5, bounds=[1, 10])
    # character = bch.StringSweep(["a", "b"])

    text_vid = bch.ResultVideo()
    frame_width = bch.ResultVar("pixels")
    frame_height = bch.ResultVar("pixels")
    duration = bch.ResultVar("S")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # if self.labels:
        # var_name = "sides"
        # var_value = self.sides
        vr = bch.ComposableContainerVideo()

        for c in ["a", "b"]:
            res = super().__call__(character=c)
            vr.append(res["image"])

        vid = vr.render(
            bch.RenderCfg(
                compose_method=self.compose_method,
                # var_name=var_name,
                # var_value=var_value,
                max_frame_duration=2.0,
                # max_frame_duration=1.,
                # duration=1.
            )
        )

        self.frame_width, self.frame_height = vid.size
        self.duration = vid.duration
        print("RES", self.frame_width, self.frame_height, self.duration)

        self.text_vid = VideoWriter().write_video_raw(vid)
        return self.get_results_values_as_dict()


# class BenchComposableContainerVideo(bch.ParametrizedSweep):
#     unequal_length = bch.BoolSweep()
#     compose_method = bch.EnumSweep(bch.ComposeType)
#     labels = bch.BoolSweep()
#     polygon_vid = bch.ResultVideo()

#     def __call__(self, **kwargs):
#         self.update_params_from_kwargs(**kwargs)
#         vr = bch.ComposableContainerVideo()
#         for i in range(3, 5):
#             num_frames = i * 10 if self.unequal_length else 5
#             res = BenchComposableContainerImage().__call__(
#                 compose_method=bch.ComposeType.sequence, sides=i, num_frames=num_frames
#             )
#             vr.append(res["polygon_vid"])

#         self.polygon_vid = vr.to_video(bch.RenderCfg(compose_method=kwargs.get("compose_method")))
#         return self.get_results_values_as_dict()


def example_composable_container_image(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchComposableContainerImage().to_bench(run_cfg)
    bench.result_vars = ["text_vid", "duration"]
    # bench.result_vars = ["duration"]
    # bench.add_plot_callback(bch.BenchResult.to_panes)
    # bench.add_plot_callback(bch.BenchResult.to_table)

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


# def example_composable_container_video(
#     run_cfg: bch.BenchRunCfg | None = None
# ) -> bch.Bench:
#     bench = BenchComposableContainerVideo().to_bench(run_cfg)

#     bench.result_vars = ["polygon_vid"]
#     bench.add_plot_callback(bch.BenchResult.to_panes)
#     bench.add_plot_callback(bch.BenchResult.to_video_grid, result_types=(bch.ResultVideo))
#     bench.add_plot_callback(bch.BenchResult.to_video_summary, result_types=(bch.ResultVideo))
#     bench.plot_sweep(input_vars=["compose_method", "labels"], const_vars=dict(unequal_length=True))

#     res = bench.plot_sweep(
#         input_vars=[],
#         const_vars=dict(unequal_length=False, compose_method=bch.ComposeType.sequence),
#         plot_callbacks=False,
#     )

#     bench.report.append(res.to_video_grid())

#     return bench


# if __name__ == "__main__":
#     ex_run_cfg = bch.BenchRunCfg()
#     ex_run_cfg.cache_samples = False
#     # ex_run_cfg.level = 2
#     ex_report = bch.BenchReport()
#     example_composable_container_image(ex_run_cfg, )
#     # example_composable_container_video(ex_run_cfg, )
#     ex_report.show()


if __name__ == "__main__":
    bench_runner = bch.BenchRunner("ImageChar")
    # bench_runner.add_run(bench_image)
    bench_runner.add_run(example_composable_container_image)

    bench_runner.run(level=6, show=True, cache_results=False)
