"""Meta-generator: Fidelity System.

Demonstrates how the fidelity parameter controls sampling density.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "levels"


class MetaLevels(MetaGeneratorBase):
    """Generate Python example demonstrating the fidelity sampling system."""

    def benchmark(self):
        imports = "import bencher as bn\nfrom bencher.example.meta.example_meta import BenchMeta"
        levels_desc = (
            "Fidelity levels let you perform parameter sweeps without "
            "having to decide how many samples to take when defining the class. "
            "If you perform a sweep at fidelity 2, all those points are reused when "
            "sampling at fidelity 3. Higher fidelity reuses the points from lower "
            "fidelity to avoid recomputing potentially expensive samples. This "
            "enables a workflow where you quickly see results at low resolution "
            "to sense-check the code, then run at a high fidelity for full "
            "detail. When calling a sweep at a high fidelity you can publish "
            "intermediate lower-fidelity results as computation continues, letting "
            "you track progress and end the sweep early when you have "
            "sufficient resolution."
        )
        levels_post = (
            "Each panel shows the benchmark sampled at a different fidelity. "
            "Higher fidelity produces more sample points. Notice how lower-fidelity "
            "sample points are a subset of higher-fidelity points -- no work is wasted."
        )
        body = (
            "bench = BenchMeta().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Using Fidelity to define sample density",\n'
            "    input_vars=[\n"
            '        bn.sweep("float_vars", [1, 2]),\n'
            '        bn.sweep("fidelity", [2, 3, 4, 5]),\n'
            "    ],\n"
            "    const_vars=dict(categorical_vars=0),\n"
            f"    description={levels_desc!r},\n"
            f"    post_description={levels_post!r},\n"
            ")\n"
        )
        self.generate_example(
            title="Fidelity System: Sample Density",
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
        title="Fidelity System",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_levels)
