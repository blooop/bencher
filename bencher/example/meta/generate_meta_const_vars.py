"""Meta-generator: Constant Variable Slicing.

Shows fixing parameters to slice a high-dimensional space.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "const_vars"


class MetaConstVars(MetaGeneratorBase):
    """Generate Python examples demonstrating const_vars usage."""

    n_const = bch.IntSweep(default=0, bounds=(0, 2), doc="Number of constant variables")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"const_vars_{self.n_const}"
        function_name = f"example_const_vars_{self.n_const}"
        title = f"Constant Variables: {self.n_const} fixed parameter(s)"

        if self.n_const == 0:
            input_vars_code = '["float1", "float2", "float3"]'
            const_vars_code = ""
        elif self.n_const == 1:
            input_vars_code = '["float1", "float2"]'
            const_vars_code = ", const_vars=dict(float3=0.5)"
        else:
            input_vars_code = '["float1"]'
            const_vars_code = ", const_vars=dict(float2=0.5, float3=0.5)"

        imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )

        body = (
            f"    run_cfg.level = 3\n"
            f"    benchable = BenchableObject()\n"
            f"    bench = benchable.to_bench(run_cfg)\n"
            f"    bench.plot_sweep(input_vars={input_vars_code}, "
            f'result_vars=["distance"]{const_vars_code})\n'
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


def example_meta_const_vars(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaConstVars().to_bench(run_cfg)

    bench.plot_sweep(
        title="Constant Variable Slicing",
        input_vars=[bch.p("n_const", [0, 1, 2])],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_const_vars)
