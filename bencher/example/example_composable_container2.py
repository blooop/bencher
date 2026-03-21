import bencher as bn
from PIL import Image, ImageDraw
from bencher.video_writer import VideoWriter


class BenchImageTest(bn.ParametrizedSweep):
    character = bn.StringSweep(["a", "b", "c", "d", "e", "f"])
    r = bn.IntSweep(default=255, bounds=[0, 255])
    g = bn.IntSweep(default=255, bounds=[0, 255])
    b = bn.IntSweep(default=255, bounds=[0, 255])
    width = bn.IntSweep(default=100, bounds=[10, 100])
    height = bn.IntSweep(default=100, bounds=[10, 100])

    image = bn.ResultImage()

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
        self.image = bn.gen_image_path()
        img.save(self.image)
        return super().__call__(**kwargs)


def bench_image(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchImageTest().to_bench(run_cfg)
    bench.sweep_sequential(group_size=1)
    return bench


class BenchComposableContainerImage(BenchImageTest):
    compose_method = bn.EnumSweep(bn.ComposeType)
    labels = bn.BoolSweep()
    # num_frames = bn.IntSweep(default=5, bounds=[1, 10])
    # character = bn.StringSweep(["a", "b"])

    text_vid = bn.ResultVideo()
    frame_width = bn.ResultVar("pixels")
    frame_height = bn.ResultVar("pixels")
    duration = bn.ResultVar("S")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # if self.labels:
        # var_name = "sides"
        # var_value = self.sides
        vr = bn.ComposableContainerVideo()

        for c in ["a", "b"]:
            res = super().__call__(character=c)
            vr.append(res["image"])

        vid = vr.render(
            bn.RenderCfg(
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


# class BenchComposableContainerVideo(bn.ParametrizedSweep):
#     unequal_length = bn.BoolSweep()
#     compose_method = bn.EnumSweep(bn.ComposeType)
#     labels = bn.BoolSweep()
#     polygon_vid = bn.ResultVideo()

#     def __call__(self, **kwargs):
#         self.update_params_from_kwargs(**kwargs)
#         vr = bn.ComposableContainerVideo()
#         for i in range(3, 5):
#             num_frames = i * 10 if self.unequal_length else 5
#             res = BenchComposableContainerImage().__call__(
#                 compose_method=bn.ComposeType.sequence, sides=i, num_frames=num_frames
#             )
#             vr.append(res["polygon_vid"])

#         self.polygon_vid = vr.to_video(bn.RenderCfg(compose_method=kwargs.get("compose_method")))
#         return self.get_results_values_as_dict()


def example_composable_container_image(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchComposableContainerImage().to_bench(run_cfg)
    bench.result_vars = ["text_vid", "duration"]
    # bench.result_vars = ["duration"]
    # bench.add_plot_callback(bn.BenchResult.to_panes)
    # bench.add_plot_callback(bn.BenchResult.to_table)

    # bench.add_plot_callback(bn.BenchResult.to_video_grid, result_types=(bn.ResultVideo))
    # bench.add_plot_callback(bn.BenchResult.to_video_summary, result_types=(bn.ResultVideo))
    # bench.plot_sweep(input_vars=["compose_method", "labels"])

    bench.plot_sweep(input_vars=["compose_method"])

    # bench.compose_
    # bench.plot_sweep(
    # input_vars=[bn.p("num_frames", [2, 8, 20])],
    # const_vars=dict(compose_method=bn.ComposeType.sequence),
    # )

    return bench


# def example_composable_container_video(
#     run_cfg: bn.BenchRunCfg | None = None
# ) -> bn.Bench:
#     bench = BenchComposableContainerVideo().to_bench(run_cfg)

#     bench.result_vars = ["polygon_vid"]
#     bench.add_plot_callback(bn.BenchResult.to_panes)
#     bench.add_plot_callback(bn.BenchResult.to_video_grid, result_types=(bn.ResultVideo))
#     bench.add_plot_callback(bn.BenchResult.to_video_summary, result_types=(bn.ResultVideo))
#     bench.plot_sweep(input_vars=["compose_method", "labels"], const_vars=dict(unequal_length=True))

#     res = bench.plot_sweep(
#         input_vars=[],
#         const_vars=dict(unequal_length=False, compose_method=bn.ComposeType.sequence),
#         plot_callbacks=False,
#     )

#     bench.report.append(res.to_video_grid())

#     return bench


# if __name__ == "__main__":
#     ex_run_cfg = bn.BenchRunCfg()
#     ex_run_cfg.cache_samples = False
#     # ex_run_cfg.level = 2
#     ex_report = bn.BenchReport()
#     example_composable_container_image(ex_run_cfg, )
#     # example_composable_container_video(ex_run_cfg, )
#     ex_report.show()


if __name__ == "__main__":
    bn.run(example_composable_container_image, level=6, cache_results=False)
