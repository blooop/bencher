"""Meta-generator: Level System.

Demonstrates how the level parameter controls sampling density.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "levels"


class MetaLevels(MetaGeneratorBase):
    """Generate Python example demonstrating the level sampling system."""

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        imports = "import bencher as bn\nfrom bencher.example.meta.example_meta import BenchMeta"
        levels_desc = (
            "Sample levels let you perform parameter sweeps without "
            "having to decide how many samples to take when defining the class. "
            "If you perform a sweep at level 2, all those points are reused when "
            "sampling at level 3. Higher levels reuse the points from lower "
            "levels to avoid recomputing potentially expensive samples. This "
            "enables a workflow where you quickly see results at low resolution "
            "to sense-check the code, then run at a high level for full "
            "fidelity. When calling a sweep at a high level you can publish "
            "intermediate lower-level results as computation continues, letting "
            "you track progress and end the sweep early when you have "
            "sufficient resolution."
        )
        levels_post = (
            "Each panel shows the benchmark sampled at a different level. "
            "Higher levels produce more sample points. Notice how lower-level "
            "sample points are a subset of higher-level points -- no work is wasted."
        )
        body = (
            "bench = BenchMeta().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            '    title="Using Levels to define sample density",\n'
            "    input_vars=[\n"
            '        bn.sweep("float_vars", [1, 2]),\n'
            '        bn.sweep("level", [2, 3, 4, 5]),\n'
            "    ],\n"
            "    const_vars=dict(categorical_vars=0),\n"
            f"    description={levels_desc!r},\n"
            f"    post_description={levels_post!r},\n"
            ")\n"
        )
        self.generate_example(
            title="Level System: Sample Density",
            output_dir=OUTPUT_DIR,
            filename="levels_sample_density",
            function_name="example_levels_sample_density",
            imports=imports,
            body=body,
            class_code="",
        )

        return super().__call__()


def example_meta_levels(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaLevels().to_bench(run_cfg)

    bench.plot_sweep(
        title="Level System",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_levels)
