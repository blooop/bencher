import bencher as bch
from bencher.example.meta.example_meta import BenchMeta


def example_levels(run_cfg: bch.BenchRunCfg = None, report: bch.BenchReport = None) -> bch.Bench:
    bench = BenchMeta().to_bench(run_cfg, report)

    bench.plot_sweep(
        title="Using Levels to define sample density",
        description="Sample levels let you perform parameter sweeps without having to decide how many samples to take when defining the class.  If you perform a sweep at level 2, then all the points are reused when sampling at level 3.  The higher levels reuse the points from lower levels to avoid having to recompute potentially expensive samples. The other advantage is that it enables a workflow where you can quickly see the results of the sweep at a low resolution to sense check the code, and then run it at a high level to get the fidelity you want.  When calling a sweep at a high level, you can publish the intermediate lower level results as the computiation continues so that you can track the progress of the computation and end the sweep early when you have sufficient resolution",
        input_vars=[
            bch.p("float_vars", [1, 2]),
            bch.p("level", [2, 3, 4, 5]),
        ],
        const_vars=[
            BenchMeta.param.categorical_vars.with_const(0),
        ],
    )
    return bench


if __name__ == "__main__":
    example_levels().report.show()
