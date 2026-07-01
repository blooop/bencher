"""Auto-generated example: Subsampling Divisions System: Sample Density."""

import bencher as bn
from bencher.example.meta.example_meta import BenchMeta


def example_levels_sample_density(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Subsampling Divisions System: Sample Density."""
    bench = BenchMeta().to_bench(run_cfg)
    bench.plot_sweep(
        title="Using Subsampling Divisions to define sample density",
        input_vars=[
            bn.sweep("float_vars", [1, 2]),
            bn.sweep("subsampling_divisions", [2, 3, 4, 5]),
        ],
        const_vars=dict(categorical_vars=0),
        description="Subsampling divisions let you perform parameter sweeps without having to decide how many samples to take when defining the class. If you perform a sweep at subsampling_divisions=2, all those points are reused when sampling at subsampling_divisions=3. Higher values reuse the points from lower ones to avoid recomputing potentially expensive samples. This enables a workflow where you quickly see results at low resolution to sense-check the code, then run at a high value for full detail. When calling a sweep at a high subsampling_divisions you can publish intermediate lower-resolution results as computation continues, letting you track progress and end the sweep early when you have sufficient resolution.",
        post_description="Each panel shows the benchmark sampled at a different subsampling_divisions value. Higher values produce more sample points. Notice how lower sample points are a subset of higher ones -- no work is wasted.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_levels_sample_density)
