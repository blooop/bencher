import nbformat as nbf
from typing import Any
import bencher as bch


from bencher.example.meta.example_meta import BenchableObject


class BenchMetaGen(bch.ParametrizedSweep):
    """This class uses bencher to display the multidimensional types bencher can represent"""

    # Benchable object to use
    benchable_obj = None  # Will store the benchable object instance

    # Variables for controlling the sweep
    float_vars_count = bch.IntSweep(
        default=0, bounds=(0, 3), doc="The number of floating point variables that are swept"
    )
    categorical_vars_count = bch.IntSweep(
        default=0, bounds=(0, 2), doc="The number of categorical variables that are swept"
    )

    # Lists to store the actual variable names
    float_var_names = []  # Will store float variable names
    categorical_var_names = []  # Will store categorical variable names
    result_var_names = []  # Will store result variable names

    # Configuration options
    sample_with_repeats = bch.IntSweep(default=1, bounds=(1, 100))
    sample_over_time = bch.BoolSweep(default=False)
    level = bch.IntSweep(default=2, units="level", bounds=(2, 5))
    run_bench = False

    plots = bch.ResultReference(units="int")

    def __init__(
        self, benchable_obj=None, float_vars=None, categorical_vars=None, result_vars=None, **params
    ):
        """Initialize with a benchable object and variable specifications

        Args:
            benchable_obj: The benchable object to use
            float_vars: List of float variable names to sweep
            categorical_vars: List of categorical variable names to sweep
            result_vars: List of result variable names to plot
            **params: Additional parameters
        """
        super().__init__(**params)

        # Set the benchable object
        self.benchable_obj = benchable_obj if benchable_obj is not None else BenchableObject()

        # Dynamically discover parameters from the benchable object
        float_param_names = []
        categorical_param_names = []
        result_param_names = []

        # Check all parameters of the benchable object
        for name, param in self.benchable_obj.__class__.param.objects().items():
            if hasattr(param, "bounds") and isinstance(param, bch.FloatSweep):
                float_param_names.append(name)
            elif isinstance(param, (bch.BoolSweep, bch.EnumSweep, bch.StringSweep)):
                categorical_param_names.append(name)
            elif isinstance(param, bch.ResultVar):
                result_param_names.append(name)

        # Use provided parameter lists or discovered ones
        self.float_var_names = float_vars if float_vars is not None else float_param_names
        self.categorical_var_names = (
            categorical_vars if categorical_vars is not None else categorical_param_names
        )
        self.result_var_names = result_vars if result_vars is not None else result_param_names

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        run_cfg = bch.BenchRunCfg()
        run_cfg.level = self.level
        run_cfg.repeats = self.sample_with_repeats
        run_cfg.over_time = self.sample_over_time
        run_cfg.plot_size = 500

        # Limit the variables to the specified counts
        float_vars = []
        # Apply the max_level=3 limit to the 3rd and subsequent float variables
        for i, var_name in enumerate(self.float_var_names[: self.float_vars_count]):
            if i >= 2:  # Third variable (index 2) and beyond
                float_vars.append(bch.p(var_name, max_level=3))
            else:
                float_vars.append(var_name)

        categorical_vars = self.categorical_var_names[: self.categorical_vars_count]
        input_vars = float_vars + categorical_vars

        if self.run_bench and input_vars and self.result_var_names:
            bench = self.benchable_obj.to_bench(run_cfg)
            res = bench.plot_sweep(
                "test",
                input_vars=input_vars,
                result_vars=self.result_var_names,
                plot_callbacks=False,
            )
            self.plots = bch.ResultReference()
            self.plots.obj = res.to_auto()

        title = f"{self.float_vars_count}_float_{self.categorical_vars_count}_cat"

        nb = nbf.v4.new_notebook()
        text = f"""# {title}"""

        # Customize notebook generation to use the actual benchmark object and variables
        module_import = "import bencher as bch\n"
        if self.benchable_obj.__class__.__module__ != "__main__":
            benchmark_import = f"from {self.benchable_obj.__class__.__module__} import {self.benchable_obj.__class__.__name__}\n"
        else:
            # If it's from main, use BenchableObject as fallback
            benchmark_import = "from bencher.example.meta.example_meta import BenchableObject\n"

        code_gen = f"""
%%capture
{module_import}
{benchmark_import}
run_cfg = bch.BenchRunCfg()
run_cfg.repeats = {self.sample_with_repeats}
run_cfg.level = 4 
bench = {self.benchable_obj.__class__.__name__}().to_bench(run_cfg)
res=bench.plot_sweep(input_vars={input_vars},
                    result_vars={self.result_var_names})
"""
        code_results = """
from bokeh.io import output_notebook
output_notebook()
res.to_auto_plots()
"""

        nb["cells"] = [
            nbf.v4.new_markdown_cell(text),
            nbf.v4.new_code_cell(code_gen),
            nbf.v4.new_code_cell(code_results),
        ]
        from pathlib import Path

        fname = Path(f"docs/reference/Meta/ex_{title}.ipynb")
        fname.parent.mkdir(parents=True, exist_ok=True)
        fname.write_text(nbf.writes(nb), encoding="utf-8")

        return super().__call__()


def example_meta(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = BenchMetaGen().to_bench(run_cfg)

    bench.plot_sweep(
        title="Meta Bench",
        description="""## All Combinations of Variable Sweeps and Resulting Plots
This uses bencher to display all the combinations of plots bencher is able to produce""",
        input_vars=[
            bch.p("float_vars_count", [0, 1]),
            "categorical_vars_count",
            bch.p("sample_with_repeats", [1, 20]),
        ],
        const_vars=[
            # ("float_vars_count", 1),
            # ("sample_with_repeats", 2),
            # ("categorical_vars_count", 2),
            # ("sample_over_time", True),
        ],
    )
    bench.plot_sweep(
        title="Meta Bench",
        description="""## All Combinations of Variable Sweeps and Resulting Plots
This uses bencher to display all the combinations of plots bencher is able to produce""",
        input_vars=[
            bch.p("float_vars_count", [2, 3]),
            "categorical_vars_count",
        ],
    )

    #     bench.plot_sweep(
    #         title="Meta Bench",
    #         description="""## All Combinations of Variable Sweeps and Resulting Plots
    # This uses bencher to display all the combinations of plots bencher is able to produce""",
    #         input_vars=[
    #             bch.p("float_vars_count", [2, 3]),
    #             "categorical_vars_count",
    #         ],
    #         const_vars=[
    #             dict(level=3)
    #             # ("sample_with_repeats", 2),
    #             # ("categorical_vars_count", 2),
    #             # ("sample_over_time", True),
    #         ],
    #     )

    return bench


if __name__ == "__main__":
    example_meta().report.show()
