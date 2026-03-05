from typing import Any

import bencher as bch
from bencher.example.meta.example_meta import BenchableObject
from bencher.example.meta.meta_generator_base import MetaGeneratorBase


class BenchMetaGen(bch.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    # Benchable object to use
    benchable_obj = None  # Will store the benchable object instance

    # Variables for controlling the sweep
    float_vars_count = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of floating point variables that are swept"
    )
    categorical_vars_count = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of categorical variables that are swept"
    )

    # Lists to store the actual variable names (initialized in __init__)
    float_var_names = None
    categorical_var_names = None
    result_var_names = None

    # Configuration options
    sample_with_repeats = bch.IntSweep(default=1, bounds=(1, 100))
    sample_over_time = bch.BoolSweep(default=False)
    level = bch.IntSweep(default=2, units="level", bounds=(2, 5))
    run_bench = False

    plots = bch.ResultReference(units="int")

    def __init__(
        self, benchable_obj=None, float_vars=None, categorical_vars=None, result_vars=None, **params
    ):
        super().__init__(**params)

        self.benchable_obj = benchable_obj if benchable_obj is not None else BenchableObject()

        float_param_names = []
        categorical_param_names = []
        result_param_names = []

        # noise_scale is a FloatSweep used as a const_var, not a sweep input
        skip = {"noise_scale"}
        for name, param in self.benchable_obj.__class__.param.objects().items():
            if name in skip:
                continue
            if hasattr(param, "bounds") and isinstance(param, bch.FloatSweep):
                float_param_names.append(name)
            elif isinstance(param, (bch.BoolSweep, bch.EnumSweep, bch.StringSweep)):
                categorical_param_names.append(name)
            elif isinstance(param, bch.ResultVar):
                result_param_names.append(name)

        self.float_var_names = float_vars if float_vars is not None else float_param_names
        self.categorical_var_names = (
            categorical_vars if categorical_vars is not None else categorical_param_names
        )
        self.result_var_names = result_vars if result_vars is not None else result_param_names

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        if hasattr(self.benchable_obj, "noise_scale") and self.sample_with_repeats > 1:
            self.benchable_obj.noise_scale = 0.15

        # Build input variable lists
        float_vars = []
        for i, var_name in enumerate(self.float_var_names[: self.float_vars_count]):
            if i >= 2:
                float_vars.append(bch.p(var_name, max_level=3))
            else:
                float_vars.append(var_name)

        categorical_vars = self.categorical_var_names[: self.categorical_vars_count]
        input_vars = float_vars + categorical_vars

        base_title = f"{self.float_vars_count}_float_{self.categorical_vars_count}_cat"

        if self.sample_over_time:
            variant = "over_time"
        elif self.sample_with_repeats > 1:
            variant = "with_repeats"
        else:
            variant = "no_repeats"

        # Determine benchable class info
        obj_class = self.benchable_obj.__class__.__name__
        if self.benchable_obj.__class__.__module__ != "__main__":
            benchmark_import = f"from {self.benchable_obj.__class__.__module__} import {obj_class}"
        else:
            benchmark_import = "from bencher.example.meta.example_meta import BenchableObject"

        title = f"{self.float_vars_count} Float, {self.categorical_vars_count} Categorical"
        function_name = f"example_{variant}_{base_title}"
        filename = f"ex_{base_title}"

        if self.sample_over_time:
            noise_val = max(0.1, 0.15 if self.sample_with_repeats > 1 else 0.0)
            repeat_lines = (
                f"run_cfg.repeats = {self.sample_with_repeats}\n"
                if self.sample_with_repeats > 1
                else ""
            )
            body = (
                f"{repeat_lines}"
                f"run_cfg.over_time = True\n"
                f"benchable = {obj_class}()\n"
                f"bench = benchable.to_bench(run_cfg)\n"
                f"time_offsets = [0.0, 0.5, 1.0]\n"
                f"_base_time = datetime(2000, 1, 1)\n"
                f"for i, offset in enumerate(time_offsets):\n"
                f"    benchable._time_offset = offset\n"
                f"    run_cfg.clear_cache = True\n"
                f"    run_cfg.clear_history = i == 0\n"
                f"    res = bench.plot_sweep(\n"
                f'        "over_time",\n'
                f"        input_vars={input_vars},\n"
                f"        result_vars={self.result_var_names},\n"
                f"        const_vars=dict(noise_scale={noise_val}),\n"
                f"        run_cfg=run_cfg,\n"
                f"        time_src=_base_time + timedelta(seconds=i),\n"
                f"    )\n"
            )
            extra_imports = "\nfrom datetime import datetime, timedelta"
        else:
            noise_const = (
                ", const_vars=dict(noise_scale=0.15)" if self.sample_with_repeats > 1 else ""
            )
            lines = []
            if self.sample_with_repeats > 1:
                lines.append(f"run_cfg.repeats = {self.sample_with_repeats}")
            lines.append(f"benchable = {obj_class}()")
            lines.extend(
                [
                    "bench = benchable.to_bench(run_cfg)",
                    "res = bench.plot_sweep(",
                    f"    input_vars={input_vars},",
                    f"    result_vars={self.result_var_names}{noise_const},",
                    ")",
                ]
            )
            body = "\n".join(lines) + "\n"
            extra_imports = ""

        imports = f"import bencher as bch\n{benchmark_import}{extra_imports}"

        gen = MetaGeneratorBase()
        gen.generate_example(
            title=title,
            output_dir=f"{self.float_vars_count}_float/{variant}",
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            main_extra=", level=4",
        )

        return super().__call__()


def example_meta(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchMetaGen().to_bench(run_cfg)

    sweep_desc = (
        """Plot gallery showing all combinations of float and categorical input variables"""
    )

    few_cats = bch.p("categorical_vars_count", [0, 1, 2])

    bench.plot_sweep(
        title="Single Sample (0-1 float vars)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=1, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Single Sample (2-3 float vars)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=1, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Repeated Samples (10x)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=10, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Repeated Samples (3x)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=3, sample_over_time=False),
    )
    bench.plot_sweep(
        title="Over Time 0-1 float (3 Snapshots)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [0, 1]), "categorical_vars_count"],
        const_vars=dict(sample_with_repeats=1, sample_over_time=True),
    )
    bench.plot_sweep(
        title="Over Time 2-3 float (3 Snapshots)",
        description=sweep_desc,
        input_vars=[bch.p("float_vars_count", [2, 3]), few_cats],
        const_vars=dict(sample_with_repeats=1, sample_over_time=True),
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta)
