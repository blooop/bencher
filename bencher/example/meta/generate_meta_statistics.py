"""Meta-generator: Statistics & Repeats.

Shows progression from single sample to error bars to distributions.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "statistics"


class MetaStatistics(MetaGeneratorBase):
    """Generate Python examples demonstrating repeat-based statistics."""

    repeats = bch.IntSweep(default=1, bounds=(1, 100), doc="Number of repeats")
    input_dims = bch.IntSweep(default=0, bounds=(0, 1), doc="0 = categorical only, 1 = float sweep")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        dim_label = "0d_categorical" if self.input_dims == 0 else "1d_float"
        filename = f"stats_{dim_label}_repeats_{self.repeats}"
        function_name = f"example_stats_{dim_label}_repeats_{self.repeats}"
        title = (
            f"Statistics: {self.repeats} repeat(s), "
            f"{'categorical' if self.input_dims == 0 else '1D float'}"
        )

        if self.input_dims == 0:
            input_vars_code = '["wave"]'
        else:
            input_vars_code = '["float1"]'

        noise_line = ""
        if self.repeats > 1:
            noise_line = "    benchable.noise_scale = 0.15\n"

        imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )

        body = (
            f"    run_cfg.repeats = {self.repeats}\n"
            f"    run_cfg.level = 3\n"
            f"    benchable = BenchableObject()\n"
            f"{noise_line}"
            f"    bench = benchable.to_bench(run_cfg)\n"
            f'    bench.plot_sweep(input_vars={input_vars_code}, result_vars=["distance"])\n'
        )

        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
        )

        return super().__call__()


def example_meta_statistics(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaStatistics().to_bench(run_cfg)

    bench.plot_sweep(
        title="Statistics: categorical only",
        input_vars=[bch.p("repeats", [1, 5, 20]), bch.p("input_dims", [0])],
    )
    bench.plot_sweep(
        title="Statistics: 1D float sweep",
        input_vars=[bch.p("repeats", [1, 5, 20]), bch.p("input_dims", [1])],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_statistics)
