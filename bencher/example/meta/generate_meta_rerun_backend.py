"""Meta-generator: Rerun Backend examples.

Shows ``res.to_rerun()`` for various dimensionality configurations,
demonstrating the rerun visualization backend for N-dimensional benchmark results.
"""

from typing import Any

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "rerun_backend"

_DEFAULT_CLASS = "BenchableObject"
_DEFAULT_MODULE = "bencher.example.meta.example_meta"

RERUN_CONFIGS = {
    "rerun_0d": {
        "float_dims": 0,
        "cat_dims": 0,
        "repeats": 1,
    },
    "rerun_1d_float": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 1,
    },
    "rerun_2d_float": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
    },
    "rerun_3d_float": {
        "float_dims": 3,
        "cat_dims": 0,
        "repeats": 1,
    },
    "rerun_1d_cat": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
    },
    "rerun_float_cat": {
        "float_dims": 1,
        "cat_dims": 1,
        "repeats": 1,
    },
    "rerun_curve": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 5,
    },
    "rerun_scatter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
    },
    "rerun_histogram": {
        "float_dims": 0,
        "cat_dims": 0,
        "repeats": 10,
    },
}

RERUN_NAMES = list(RERUN_CONFIGS.keys())

_FLOAT_VARS = ["float1", "float2", "float3"]
_CAT_VARS = ["wave", "variant"]


def _input_vars_for(cfg: dict) -> str:
    """Build the input_vars code string from float_dims and cat_dims counts."""
    names = _FLOAT_VARS[: cfg["float_dims"]] + _CAT_VARS[: cfg["cat_dims"]]
    return repr(names)


class MetaRerunBackend(MetaGeneratorBase):
    """Generate Python examples demonstrating the rerun backend."""

    rerun_config = bn.StringSweep(RERUN_NAMES, doc="Rerun example configuration")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        cfg = RERUN_CONFIGS[self.rerun_config]
        filename = self.rerun_config
        function_name = f"example_{self.rerun_config}"
        title = f"Rerun Backend: {self.rerun_config.replace('_', ' ').title()}"

        input_vars = _input_vars_for(cfg)
        const_vars = "dict(noise_scale=0.15)" if cfg["repeats"] > 1 else None

        level = 2 if cfg["float_dims"] >= 2 else 3
        run_kwargs = {"level": level}
        if cfg["repeats"] > 1:
            run_kwargs["repeats"] = cfg["repeats"]

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=_DEFAULT_CLASS,
            benchable_module=_DEFAULT_MODULE,
            input_vars=input_vars,
            result_vars='["distance"]',
            const_vars=const_vars,
            post_sweep_line="res.to_rerun()",
            run_kwargs=run_kwargs,
        )

        return super().__call__()


def example_meta_rerun_backend(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaRerunBackend().to_bench(run_cfg)

    bench.plot_sweep(
        title="Rerun Backend",
        input_vars=[bn.p("rerun_config", RERUN_NAMES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_rerun_backend)
