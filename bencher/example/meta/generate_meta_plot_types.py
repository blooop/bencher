"""Meta-generator: Explicit Plot Conversions.

Shows ``res.to_<plot_type>()`` for each plot type with appropriate data.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "plot_types"

# Each plot type maps to the sweep config needed to satisfy its VarRange constraints
PLOT_CONFIGS = {
    "bar": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "result_code": "res.to_bar()",
        "input_vars": '["wave"]',
    },
    "line": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 1,
        "result_code": "res.to_line()",
        "input_vars": '["float1"]',
    },
    "curve": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 5,
        "result_code": "res.to_curve()",
        "input_vars": '["float1"]',
    },
    "scatter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "result_code": "res.to_scatter()",
        "input_vars": '["wave"]',
    },
    "heatmap": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "result_code": "res.to_heatmap()",
        "input_vars": '["float1", "float2"]',
    },
    "surface": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "result_code": "res.to_surface()",
        "input_vars": '["float1", "float2"]',
    },
    "box_whisker": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
        "result_code": "from bencher.results.holoview_results.distribution_result.box_whisker_result import BoxWhiskerResult\nres.to(BoxWhiskerResult)",
        "input_vars": '["wave"]',
    },
    "scatter_jitter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
        "result_code": "from bencher.results.holoview_results.distribution_result.scatter_jitter_result import ScatterJitterResult\nres.to(ScatterJitterResult)",
        "input_vars": '["wave"]',
    },
}

PLOT_NAMES = list(PLOT_CONFIGS.keys())


class MetaPlotTypes(MetaGeneratorBase):
    """Generate notebooks demonstrating each plot type."""

    plot_type = bch.StringSweep(PLOT_NAMES, doc="Plot type to demonstrate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        cfg = PLOT_CONFIGS[self.plot_type]
        filename = f"plot_{self.plot_type}"
        title = f"Plot Type: {self.plot_type.replace('_', ' ').title()}"

        level = 2 if cfg["float_dims"] >= 2 else 3
        noise_line = ""
        if cfg["repeats"] > 1:
            noise_line = "benchable.noise_scale = 0.15\n"

        setup_code = (
            "import bencher as bch\n"
            "from bencher.example.meta.example_meta import BenchableObject\n"
            "run_cfg = bch.BenchRunCfg()\n"
            f"run_cfg.repeats = {cfg['repeats']}\n"
            f"run_cfg.level = {level}\n"
            "benchable = BenchableObject()\n"
            f"{noise_line}"
            "bench = benchable.to_bench(run_cfg)\n"
            f"res = bench.plot_sweep(input_vars={cfg['input_vars']}, "
            'result_vars=["distance"])\n'
        )

        results_code = (
            f"from bokeh.io import output_notebook\noutput_notebook()\n{cfg['result_code']}"
        )

        self.generate_notebook(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            setup_code=setup_code,
            results_code=results_code,
        )

        return super().__call__()


def example_meta_plot_types(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaPlotTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Plot Types",
        input_vars=[bch.p("plot_type", PLOT_NAMES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_plot_types)
