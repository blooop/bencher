"""Meta-generator: Subsampling Divisions System.

Demonstrates how the subsampling_divisions parameter controls sampling density.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "levels"


class MetaLevels(MetaGeneratorBase):
    """Generate Python example demonstrating the subsampling_divisions sampling system."""

    def benchmark(self):
        imports = "import bencher as bn\nfrom bencher.example.meta.example_meta import BenchMeta"
        levels_desc = (
            "Subsampling Divisions levels let you perform parameter sweeps without "
            "having to decide how many samples to take when defining the class. "
            "If you perform a sweep at subsampling_divisions 2, all those points are reused when "
            "sampling at subsampling_divisions 3. Higher subsampling_divisions reuses the points from lower "
            "subsampling_divisions to avoid recomputing potentially expensive samples. This "
            "enables a workflow where you quickly see results at low resolution "
            "to sense-check the code, then run at a high subsampling_divisions for full "
            "detail. When calling a sweep at a high subsampling_divisions you can publish "
            "intermediate lower-subsampling_divisions results as computation continues, letting "
            "you track progress and end the sweep early when you have "
            "sufficient resolution."
        )
        levels_post = (
            "Each panel shows the benchmark sampled at a different subsampling_divisions. "
            "Higher subsampling_divisions produces more sample points. Notice how lower-subsampling_divisions "
            "sample points are a subset of higher-subsampling_divisions points -- no work is wasted."
        )
        body = (
            "bench = BenchMeta().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Using Subsampling Divisions to define sample density",\n'
            "    input_vars=[\n"
            '        bn.sweep("float_vars", [1, 2]),\n'
            '        bn.sweep("subsampling_divisions", [2, 3, 4, 5]),\n'
            "    ],\n"
            "    const_vars=dict(categorical_vars=0),\n"
            f"    description={levels_desc!r},\n"
            f"    post_description={levels_post!r},\n"
            ")\n"
        )
        self.generate_example(
            title="Subsampling Divisions System: Sample Density",
            output_dir=OUTPUT_DIR,
            filename="example_levels_sample_density",
            function_name="example_levels_sample_density",
            imports=imports,
            body=body,
            class_code="",
        )


def example_meta_levels(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaLevels().to_bench(run_cfg)

    bench.plot_sweep(
        title="Subsampling Divisions System",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_levels)
