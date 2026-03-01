import rerun as rr
import bencher as bch

rr.init("rerun_example_my_blueprint")


class SweepRerun(bch.ParametrizedSweep):
    theta = bch.FloatSweep(default=1, bounds=[1, 4], doc="Input angle", units="rad", samples=30)

    out_pane = bch.ResultContainer()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_pane = bch.capture_rerun_window(width=300, height=300)
        rr.log("s1", rr.Boxes2D(half_sizes=[self.theta, 1]))

        return super().__call__(**kwargs)


def example_rerun(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """This example shows how to sample a 1 dimensional float variable and plot the result of passing that parameter sweep to the benchmarking function"""

    bench = SweepRerun().to_bench(run_cfg)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    bch.run_flask_in_thread()
    example_rerun(bch.BenchRunCfg(level=3)).report.show()
