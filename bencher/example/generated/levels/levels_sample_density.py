"""Auto-generated example: Level System: Sample Density."""

import bencher as bn
from bencher.example.meta.example_meta import BenchMeta


def example_levels_sample_density(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Level System: Sample Density."""
    bench = BenchMeta().to_bench(run_cfg)
    bench.plot_sweep(
        title="Using Levels to define sample density",
        input_vars=[
            bn.sweep("float_vars", [1, 2]),
            bn.sweep("level", [2, 3, 4, 5]),
        ],
        const_vars=dict(categorical_vars=0),
        description=(
            "Sample levels let you perform parameter sweeps without having to decide how many "
            "samples to take when defining the class. If you perform a sweep at level 2, all "
            "those points are reused when sampling at level 3. Higher levels reuse the points "
            "from lower levels to avoid recomputing potentially expensive samples. This "
            "enables a workflow where you quickly see results at low resolution to "
            "sense-check the code, then run at a high level for full fidelity. When calling a "
            "sweep at a high level you can publish intermediate lower-level results as "
            "computation continues, letting you track progress and end the sweep early when "
            "you have sufficient resolution."
        ),
        post_description=(
            "Each panel shows the benchmark sampled at a different level. Higher levels "
            "produce more sample points. Notice how lower-level sample points are a subset of "
            "higher-level points -- no work is wasted."
        ),
    )

    return bench


if __name__ == "__main__":
    bn.run(example_levels_sample_density)
