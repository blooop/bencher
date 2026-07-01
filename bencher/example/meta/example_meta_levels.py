import bencher as bn
from bencher.example.meta.example_meta import BenchMeta


def example_meta_levels(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = BenchMeta().to_bench(run_cfg)

    bench.plot_sweep(
        title="Using Subsampling Divisions to define sample density",
        description="Subsampling divisions let you perform parameter sweeps without having to decide how many samples to take when defining the class. If you perform a sweep at subsampling_divisions 2, then all the points are reused when sampling at subsampling_divisions 3. The higher subsampling_divisions reuse the points from lower ones to avoid having to recompute potentially expensive samples. The other advantage is that it enables a workflow where you can quickly see the results of the sweep at a low resolution to sense check the code, and then run it at a high subsampling_divisions for full detail. When calling a sweep at a high subsampling_divisions you can publish the intermediate lower results as the computation continues so that you can track the progress and end the sweep early when you have sufficient resolution",
        input_vars=[
            bn.sweep("float_vars", [1, 2]),
            bn.sweep("subsampling_divisions", [2, 3, 4]),
        ],
        const_vars=dict(categorical_vars=0),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_levels)
