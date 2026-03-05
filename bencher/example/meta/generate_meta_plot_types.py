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
        "plot_call": "res.to(BoxWhiskerResult)",
        "extra_import": (
            "from bencher.results.holoview_results.distribution_result"
            ".box_whisker_result import BoxWhiskerResult"
        ),
        "input_vars": '["wave"]',
    },
    "scatter_jitter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 10,
        "plot_call": "res.to(ScatterJitterResult)",
        "extra_import": (
            "from bencher.results.holoview_results.distribution_result"
            ".scatter_jitter_result import ScatterJitterResult"
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

        import_lines = [
            "import bencher as bch",
            "from bencher.example.meta.example_meta import BenchableObject",
        ]
        if cfg.get("extra_import"):
            import_lines.append(cfg["extra_import"])
        imports = "\n".join(import_lines)

        noise_const = ", const_vars=dict(noise_scale=0.15)" if cfg["repeats"] > 1 else ""
        body_lines = []
        if cfg["repeats"] > 1:
            body_lines.append(f"run_cfg.repeats = {cfg['repeats']}")
        body_lines.extend(
            [
                "benchable = BenchableObject()",
                "bench = benchable.to_bench(run_cfg)",
                (
                    f"res = bench.plot_sweep(input_vars={cfg['input_vars']},"
                    f' result_vars=["distance"]{noise_const})'
                ),
                cfg["plot_call"],
            ]
        )
        body = "\n".join(body_lines) + "\n"

        level = 2 if cfg["float_dims"] >= 2 else 3
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            imports=imports,
            body=body,
            main_extra=f", level={level}",
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
