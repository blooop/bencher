"""Meta-generator: Explicit Plot Conversions.

Shows ``res.to_<plot_type>()`` for each plot type with appropriate data.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "plot_types"

PLOT_CONFIGS = {
    "bar": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_bar()",
        "input_vars": '["wave"]',
    },
    "line": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_line()",
        "input_vars": '["float1"]',
    },
    "curve": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 5,
        "plot_call": "res.to_curve()",
        "input_vars": '["float1"]',
    },
    "scatter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_scatter()",
        "input_vars": '["wave"]',
    },
    "heatmap": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_heatmap()",
        "input_vars": '["float1", "float2"]',
    },
    "surface": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_surface()",
        "input_vars": '["float1", "float2"]',
    },
    "box_whisker": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
        "plot_call": (
            "from bencher.results.holoview_results.distribution_result"
            ".box_whisker_result import BoxWhiskerResult\n"
            "    res.to(BoxWhiskerResult)"
        ),
        "input_vars": '["wave"]',
    },
    "scatter_jitter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
        "plot_call": (
            "from bencher.results.holoview_results.distribution_result"
            ".scatter_jitter_result import ScatterJitterResult\n"
            "    res.to(ScatterJitterResult)"
        ),
        "input_vars": '["wave"]',
    },
}

PLOT_NAMES = list(PLOT_CONFIGS.keys())


class MetaPlotTypes(MetaGeneratorBase):
    """Generate Python examples demonstrating each plot type."""

    plot_type = bch.StringSweep(PLOT_NAMES, doc="Plot type to demonstrate")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        cfg = PLOT_CONFIGS[self.plot_type]
        filename = f"plot_{self.plot_type}"
        function_name = f"example_plot_{self.plot_type}"
        title = f"Plot Type: {self.plot_type.replace('_', ' ').title()}"

        level = 2 if cfg["float_dims"] >= 2 else 3
        noise_line = ""
        if cfg["repeats"] > 1:
            noise_line = "    benchable.noise_scale = 0.15\n"

        imports = (
            "import bencher as bch\nfrom bencher.example.meta.example_meta import BenchableObject"
        )

        body = (
            f"    run_cfg.repeats = {cfg['repeats']}\n"
            f"    run_cfg.level = {level}\n"
            f"    benchable = BenchableObject()\n"
            f"{noise_line}"
            f"    bench = benchable.to_bench(run_cfg)\n"
            f"    res = bench.plot_sweep(input_vars={cfg['input_vars']}, "
            f'result_vars=["distance"])\n'
            f"    {cfg['plot_call']}\n"
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


def example_meta_plot_types(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaPlotTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Plot Types",
        input_vars=[bch.p("plot_type", PLOT_NAMES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_plot_types)
