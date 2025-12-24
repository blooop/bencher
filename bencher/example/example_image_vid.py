from bencher.example.example_image import BenchPolygons
import bencher as bch


def example_image_vid(
    run_cfg: bch.BenchRunCfg | None = None, report: bch.BenchReport | None = None
) -> bch.Bench:
    bench = BenchPolygons().to_bench(run_cfg, report)
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
    # from functools import partial
    # bench.add_plot_callback(bch.BenchResult.to_video_summary)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=0)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=2)
    # bench.add_plot_callback(bch.BenchResult.to_video_grid, time_sequence_dimension=3)

    bench.plot_sweep(input_vars=["radius"])
    # res = bench.plot_sweep(input_vars=["radius"], plot=False)
    # bench.report.append(res.to_video_grid(target_duration=0.06))
    bench.plot_sweep(input_vars=["radius", "sides"])
    # bench.plot_sweep(input_vars=["radius", "sides", "linewidth"])
    # bench.plot_sweep(input_vars=["radius", "sides", "linewidth", "color"])

    return bench


if __name__ == "__main__":

    def simple(
        run_cfg: bch.BenchRunCfg | None = None, report: bch.BenchReport | None = None
    ) -> bch.Bench:  # pylint: disable=unused-argument
        bench = BenchPolygons().to_bench(bch.BenchRunCfg(level=4), report=report)
        bench.plot_sweep(input_vars=["sides"])
        bench.plot_sweep(input_vars=["sides", "color"])

        res = bench.plot_sweep(input_vars=["sides", "radius"])
        bench.report.append(res.to_heatmap(target_dimension=3))
        bench.report.append(res.to_line(target_dimension=1))

        return bench

    def example_image_vid_sequential(
        run_cfg: bch.BenchRunCfg | None = None, report: bch.BenchReport | None = None
    ) -> bch.Bench:
        bench = BenchPolygons().to_bench(run_cfg, report)
        bench.add_plot_callback(bch.BenchResult.to_title)
        bench.add_plot_callback(bch.BenchResult.to_video_grid)
        bench.sweep_sequential(input_vars=["radius", "sides", "linewidth", "color"], group_size=4)
        return bench

    # def example_image_pairs()

    # ex_run_cfg = bch.BenchRunCfg()
    # ex_run_cfg.cache_samples = True
    # # ex_run_cfg.debug = True
    # # ex_run_cfg.repeats = 2
    # ex_run_cfg.level = 4
    # # example_image_vid(ex_run_cfg).report.show()
    # simple().report.show()

    br = bch.BenchRunner()
    br.add(simple)
    br.add(example_image_vid)
    br.run(repeats=5, max_repeats=7, show=True)

    # br.show()

    # example_image_vid_sequential(ex_run_cfg).report.show()
    # example_image(ex_run_cfg).report.show()
