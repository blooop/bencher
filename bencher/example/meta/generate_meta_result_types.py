"""Meta-generator: Result Type Showcase.

Demonstrates each result type at different input dimensionalities.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "result_types"

RESULT_TYPES = [
    "result_var",
    "result_bool",
    "result_vec",
    "result_string",
    "result_path",
    "result_dataset",
]

VALID_COMBOS = {
    "result_var": [0, 1, 2],
    "result_bool": [0, 1, 2],
    "result_vec": [1, 2],
    "result_string": [0, 1],
    "result_path": [0, 1],
    "result_dataset": [1, 2],
}

BENCHABLE_MAP = {
    "result_var": {
        "class": "BenchableObject",
        "module": "bencher.example.meta.example_meta",
        "result_vars": '["distance"]',
    },
    "result_bool": {
        "class": "BenchableBoolResult",
        "module": "bencher.example.meta.benchable_objects",
        "result_vars": '["pass_rate"]',
    },
    "result_vec": {
        "class": "BenchableVecResult",
        "module": "bencher.example.meta.benchable_objects",
        "result_vars": '["position"]',
    },
    "result_string": {
        "class": "BenchableStringResult",
        "module": "bencher.example.meta.benchable_objects",
        "result_vars": '["report"]',
    },
    "result_path": {
        "class": "BenchablePathResult",
        "module": "bencher.example.meta.benchable_objects",
        "result_vars": '["file_result"]',
    },
    "result_dataset": {
        "class": "BenchableDataSetResult",
        "module": "bencher.example.meta.benchable_objects",
        "result_vars": '["result_ds"]',
    },
}

INPUT_VARS_MAP = {
    "result_var": {0: '["wave"]', 1: '["float1"]', 2: '["float1", "float2"]'},
    "result_bool": {0: '["difficulty"]', 1: '["threshold"]', 2: '["threshold", "difficulty"]'},
    "result_vec": {1: '["x"]', 2: '["x", "y"]'},
    "result_string": {0: '["label"]', 1: '["label", "value"]'},
    "result_path": {0: '["content"]', 1: '["content"]'},
    "result_dataset": {1: '["value"]', 2: '["value", "scale"]'},
}


class MetaResultTypes(MetaGeneratorBase):
    """Generate Python examples demonstrating each result type."""

    result_type = bch.StringSweep(RESULT_TYPES, doc="Result type to demonstrate")
    input_dims = bch.IntSweep(default=0, bounds=(0, 2), doc="Number of input dimensions")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if self.input_dims not in VALID_COMBOS.get(self.result_type, []):
            return super().__call__()

        info = BENCHABLE_MAP[self.result_type]
        input_vars_code = INPUT_VARS_MAP[self.result_type][self.input_dims]

        sub_dir = f"{OUTPUT_DIR}/{self.result_type}"
        filename = f"{self.result_type}_{self.input_dims}d"
        function_name = f"example_{self.result_type}_{self.input_dims}d"
        title = f"{self.result_type.replace('_', ' ').title()}: {self.input_dims}D input"

        level = 2 if self.input_dims >= 2 else 3

        imports = f"import bencher as bch\nfrom {info['module']} import {info['class']}"

        body = (
            f"    run_cfg.level = {level}\n"
            f"    benchable = {info['class']}()\n"
            f"    bench = benchable.to_bench(run_cfg)\n"
            f"    bench.plot_sweep(input_vars={input_vars_code}, "
            f"result_vars={info['result_vars']})\n"
        )

        self.generate_example(
            title=title,
            output_dir=sub_dir,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
        )

        return super().__call__()


def example_meta_result_types(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaResultTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Result Types",
        input_vars=[
            bch.p("result_type", RESULT_TYPES),
            bch.p("input_dims", [0, 1, 2]),
        ],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_result_types)
