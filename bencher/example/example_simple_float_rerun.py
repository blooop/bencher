"""Simple float example with rerun backend visualization"""

import math
import bencher as bch


class SimpleFloat(bch.ParametrizedSweep):
    theta = bch.FloatSweep(
        default=0, bounds=[0, math.pi], doc="Input angle", units="rad", samples=30
    )
    out_sin = bch.ResultVar(units="v", doc="sin of theta")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.out_sin = math.sin(self.theta)
        return super().__call__(**kwargs)


def example_simple_float_rerun(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example showing how to use rerun as a visualization backend for bencher"""

    bench = SimpleFloat().to_bench(run_cfg, report)

    # Run the parameter sweep
    results = bench.plot_sweep()

    # Add rerun visualization
    rerun_view = results.to_rerun()
    bench.report.append(rerun_view, "Rerun Visualization")

    # Also add traditional plot for comparison
    traditional_view = results.to_curve()
    bench.report.append(traditional_view, "Traditional Plot")

    return bench


def example_simple_float_rerun_only(
    run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None
) -> bch.Bench:
    """Example using only rerun visualization (no traditional plots)"""

    bench = SimpleFloat().to_bench(run_cfg, report)

    # Run the parameter sweep
    results = bench.plot_sweep()

    # Use only rerun visualization
    rerun_view = results.to_rerun()
    bench.report.append(rerun_view, "Rerun-Only Visualization")

    return bench


if __name__ == "__main__":
    # Run the example with both rerun and traditional visualization
    print("Running simple float example with rerun backend...")
    bench = example_simple_float_rerun(bch.BenchRunCfg(level=3))
    bench.report.show()
