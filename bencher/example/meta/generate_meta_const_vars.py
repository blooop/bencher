"""Meta-generator: Constant Variable Slicing.

Shows fixing parameters to slice a high-dimensional space.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "const_vars"


class MetaConstVars(MetaGeneratorBase):
    """Generate notebooks demonstrating const_vars usage."""

    n_const = bch.IntSweep(default=0, bounds=(0, 2), doc="Number of constant variables")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        filename = f"const_vars_{self.n_const}"
        param_label = "parameter" if self.n_const == 1 else "parameters"
        title = f"Constant Variables: {self.n_const} fixed {param_label}"

        if self.n_const == 0:
            input_vars_code = '["float1", "float2", "float3"]'
            const_vars_code = ""
        elif self.n_const == 1:
            input_vars_code = '["float1", "float2"]'
            const_vars_code = ", const_vars=dict(float3=0.5)"
        else:
            input_vars_code = '["float1"]'
            const_vars_code = ", const_vars=dict(float2=0.5, float3=0.5)"

        setup_code = (
            "import bencher as bch\n"
            "from bencher.example.meta.example_meta import BenchableObject\n"
            "run_cfg = bch.BenchRunCfg()\n"
            "run_cfg.level = 3\n"
            "benchable = BenchableObject()\n"
            "bench = benchable.to_bench(run_cfg)\n"
            f"res = bench.plot_sweep(input_vars={input_vars_code}, "
            f'result_vars=["distance"]{const_vars_code})\n'
        )

        self.generate_notebook(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            setup_code=setup_code,
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
