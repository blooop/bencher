"""Meta-generator: ResultBool Plot Types.

Shows ResultBool output with each plot type that supports it.
Each generated example is fully self-contained with an inline class definition.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "bool_plot_types"

# ---------------------------------------------------------------------------
# Inline class code for each plot type
# ---------------------------------------------------------------------------

_HEALTH_CHECK_CAT_CODE = """\
class HealthCheckCat(bch.ParametrizedSweep):
    \"\"\"Check service health across backends.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": True, "memcached": True, "local": False}
        self.healthy = lookup[self.backend]
        return super().__call__()"""

_HEALTH_CHECK_FLOAT_CODE = """\
import math


class HealthCheckFloat(bch.ParametrizedSweep):
    \"\"\"Check if service health exceeds a threshold.\"\"\"

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.load)
        self.healthy = score > 0.5
        return super().__call__()"""

_HEALTH_CHECK_FLOAT_NOISY_CODE = """\
import math
import random


class HealthCheckFloatNoisy(bch.ParametrizedSweep):
    \"\"\"Check health with noise — repeated runs produce different outcomes.\"\"\"

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        probability = math.sin(math.pi * self.load)
        self.healthy = random.random() < probability
        return super().__call__()"""

_HEALTH_CHECK_2D_CODE = """\
import math


class HealthCheck2D(bch.ParametrizedSweep):
    \"\"\"2D health check based on two float inputs.\"\"\"

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        score = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        self.healthy = score > 0.0
        return super().__call__()"""

_HEALTH_CHECK_2D_NOISY_CODE = """\
import math
import random


class HealthCheck2DNoisy(bch.ParametrizedSweep):
    \"\"\"2D health check with noise for repeated-run surface plots.\"\"\"

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        probability = 0.5 + 0.4 * math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        self.healthy = random.random() < probability
        return super().__call__()"""

_RELIABILITY_CAT_CODE = """\
import random


class ReliabilityCat(bch.ParametrizedSweep):
    \"\"\"Service reliability check with random outcomes per repeat.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])

    healthy = bch.ResultBool(doc="Whether the service is healthy")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        rates = {"redis": 0.95, "memcached": 0.80, "local": 0.60}
        self.healthy = random.random() < rates[self.backend]
        return super().__call__()"""

_COIN_FLIP_CODE = """\
import random


class CoinFlip(bch.ParametrizedSweep):
    \"\"\"Simple coin flip with no inputs — shows distribution of True/False.\"\"\"

    heads = bch.ResultBool(doc="Whether the coin landed heads")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.heads = random.random() < 0.5
        return super().__call__()"""

# ---------------------------------------------------------------------------
# Plot configuration table
# ---------------------------------------------------------------------------

BOOL_PLOT_CONFIGS = {
    "bar": {
        "float_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_bar()",
        "input_vars": '["backend"]',
        "result_vars": '["healthy"]',
        "benchable_class": "HealthCheckCat",
        "class_code": _HEALTH_CHECK_CAT_CODE,
    },
    "line": {
        "float_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_line()",
        "input_vars": '["load"]',
        "result_vars": '["healthy"]',
        "benchable_class": "HealthCheckFloat",
        "class_code": _HEALTH_CHECK_FLOAT_CODE,
    },
    "curve": {
        "float_dims": 1,
        "repeats": 5,
        "plot_call": "res.to_curve()",
        "input_vars": '["load"]',
        "result_vars": '["healthy"]',
        "benchable_class": "HealthCheckFloatNoisy",
        "class_code": _HEALTH_CHECK_FLOAT_NOISY_CODE,
    },
    "heatmap": {
        "float_dims": 2,
        "repeats": 1,
        "plot_call": "res.to_heatmap()",
        "input_vars": '["x", "y"]',
        "result_vars": '["healthy"]',
        "benchable_class": "HealthCheck2D",
        "class_code": _HEALTH_CHECK_2D_CODE,
    },
    "surface": {
        "float_dims": 2,
        "repeats": 2,
        "plot_call": "res.to_surface()",
        "input_vars": '["x", "y"]',
        "result_vars": '["healthy"]',
        "benchable_class": "HealthCheck2DNoisy",
        "class_code": _HEALTH_CHECK_2D_NOISY_CODE,
    },
    "violin": {
        "float_dims": 0,
        "repeats": 10,
        "plot_call": "res.to(ViolinResult)",
        "extra_import": (
            "from bencher.results.holoview_results.distribution_result"
            ".violin_result import ViolinResult"
        ),
        "input_vars": '["backend"]',
        "result_vars": '["healthy"]',
        "benchable_class": "ReliabilityCat",
        "class_code": _RELIABILITY_CAT_CODE,
    },
    "box_whisker": {
        "float_dims": 0,
        "repeats": 10,
        "plot_call": "res.to(BoxWhiskerResult)",
        "extra_import": (
            "from bencher.results.holoview_results.distribution_result"
            ".box_whisker_result import BoxWhiskerResult"
        ),
        "input_vars": '["backend"]',
        "result_vars": '["healthy"]',
        "benchable_class": "ReliabilityCat",
        "class_code": _RELIABILITY_CAT_CODE,
    },
    "scatter_jitter": {
        "float_dims": 0,
        "repeats": 10,
        "plot_call": "res.to(ScatterJitterResult)",
        "extra_import": (
            "from bencher.results.holoview_results.distribution_result"
            ".scatter_jitter_result import ScatterJitterResult"
        ),
        "input_vars": '["backend"]',
        "result_vars": '["healthy"]',
        "benchable_class": "ReliabilityCat",
        "class_code": _RELIABILITY_CAT_CODE,
    },
    "histogram": {
        "float_dims": 0,
        "repeats": 20,
        "plot_call": "res.to(HistogramResult)",
        "extra_import": "from bencher.results.histogram_result import HistogramResult",
        "input_vars": "[]",
        "result_vars": '["heads"]',
        "benchable_class": "CoinFlip",
        "class_code": _COIN_FLIP_CODE,
    },
}

BOOL_PLOT_NAMES = list(BOOL_PLOT_CONFIGS.keys())


class MetaBoolPlotTypes(MetaGeneratorBase):
    """Generate Python examples demonstrating ResultBool with each plot type."""

    plot_type = bch.StringSweep(BOOL_PLOT_NAMES, doc="Plot type to demonstrate with ResultBool")

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)

        cfg = BOOL_PLOT_CONFIGS[self.plot_type]
        filename = f"bool_plot_{self.plot_type}"
        function_name = f"example_bool_plot_{self.plot_type}"
        title = f"Bool Plot: {self.plot_type.replace('_', ' ').title()}"

        extra_imports = [cfg["extra_import"]] if cfg.get("extra_import") else None

        level = 2 if cfg["float_dims"] >= 2 else 3
        run_kwargs = {"level": level}
        if cfg["repeats"] > 1:
            run_kwargs["repeats"] = cfg["repeats"]

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=cfg["benchable_class"],
            benchable_module=None,
            input_vars=cfg["input_vars"],
            result_vars=cfg["result_vars"],
            post_sweep_line=cfg["plot_call"],
            extra_imports=extra_imports,
            run_kwargs=run_kwargs,
            class_code=cfg["class_code"],
        )

        return super().__call__()


def example_meta_bool_plot_types(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    bench = MetaBoolPlotTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Bool Plot Types",
        input_vars=[bch.p("plot_type", BOOL_PLOT_NAMES)],
    )

    return bench


if __name__ == "__main__":
    bch.run(example_meta_bool_plot_types)
