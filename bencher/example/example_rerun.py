import rerun as rr
import bencher as bn


class SweepRerun(bn.ParametrizedSweep):
    theta = bn.FloatSweep(default=1, bounds=[1, 4], doc="Input angle", units="rad", samples=30)

    out_pane = bn.ResultContainer()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        rr.log("s1", rr.Boxes2D(half_sizes=[self.theta, 1]))
        self.out_pane = bn.capture_rerun_window(width=600, height=600)

        return super().__call__(**kwargs)


def example_rerun(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Sample a 1D float variable and plot the rerun capture for each sweep point."""

    bench = SweepRerun().to_bench(run_cfg)
    bench.plot_sweep()
    return bench


if __name__ == "__main__":
    example_rerun(bn.BenchRunCfg(level=3)).report.show()
