"""Meta-generator: Statistics & Repeats.

Demonstrates how repeated sampling enables statistical visualizations:
error bands on curves, distribution plots for categorical data, and the
effect of increasing repeat count on confidence.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "statistics"


class MetaStatistics(MetaGeneratorBase):
    """Generate Python examples demonstrating repeat-based statistics."""

    example_variant = bch.IntSweep(
        default=0, bounds=(0, 2), doc="Which statistics example to generate"
    )

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.example_variant == 0:
            self._generate_error_bands()
        elif self.example_variant == 1:
            self._generate_distributions()
        else:
            self._generate_repeats_comparison()

        return super().__call__()

    def _generate_error_bands(self):
        """Error bands: mean +/- std on a 1D float sweep with repeats."""
        self.generate_sweep_example(
            title="Error Bands: mean +/- std deviation on a 1D sweep with 10 repeats",
            output_dir=OUTPUT_DIR,
            filename="stats_error_bands",
            function_name="example_stats_error_bands",
            benchable_class="BenchableObject",
            benchable_module="bencher.example.meta.example_meta",
            input_vars='["float1"]',
            result_vars='["distance", "sample_noise"]',
            const_vars="dict(noise_scale=0.3)",
            run_kwargs={"level": 4, "repeats": 10},
        )

    def _generate_distributions(self):
        """Distribution plots: box-whisker + scatter-jitter on categorical data."""
        self.generate_sweep_example(
            title="Distributions: box-whisker and scatter-jitter for categorical sweeps",
            output_dir=OUTPUT_DIR,
            filename="stats_distributions",
            function_name="example_stats_distributions",
            benchable_class="BenchableObject",
            benchable_module="bencher.example.meta.example_meta",
            input_vars='["wave", "variant"]',
            result_vars='["distance", "sample_noise"]',
            const_vars="dict(noise_scale=0.3)",
            run_kwargs={"level": 3, "repeats": 20},
        )

    def _generate_repeats_comparison(self):
        """Side-by-side comparison of 1 vs 5 vs 20 repeats on a categorical sweep."""
        title = "Repeats Comparison: 1 vs 5 vs 20 repeats on a categorical sweep"
        filename = "stats_repeats_comparison"
        function_name = "example_stats_repeats_comparison"

        imports = "\n".join(
            [
                "import bencher as bch",
                "from bencher.example.meta.example_meta import BenchableObject",
            ]
        )

        body = (
            "bench = BenchableObject().to_bench(run_cfg)\n"
            "for n_repeats in [1, 5, 20]:\n"
            "    noise = 0.3 if n_repeats > 1 else 0.0\n"
            "    sweep_cfg = bch.BenchRunCfg()\n"
            "    sweep_cfg.level = 3\n"
            "    sweep_cfg.repeats = n_repeats\n"
            "    bench.plot_sweep(\n"
            '        title=f"{n_repeats} repeat(s)",\n'
            '        input_vars=["wave"],\n'
            '        result_vars=["distance"],\n'
            "        const_vars=dict(noise_scale=noise),\n"
            "        run_cfg=sweep_cfg,\n"
            "    )\n"
        )

        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            run_kwargs={},
        )


def example_meta_statistics(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaStatistics().to_bench(run_cfg)

    bench.plot_sweep(
        title="Statistics Examples",
        input_vars=[bch.p("example_variant", [0, 1, 2])],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_statistics)
