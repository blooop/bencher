"""Meta-generator: Explicit Plot Conversions.

Shows ``res.to_<plot_type>()`` for each plot type with appropriate data.
Each generated example is fully self-contained with an inline class definition.
"""

from typing import Any

import bencher as bch
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "plot_types"

# ---------------------------------------------------------------------------
# Inline class code for each plot type
# ---------------------------------------------------------------------------

_CACHE_COMPARE_CODE = """\
class CacheCompare(bch.ParametrizedSweep):
    \"\"\"Compare response distance across cache backends.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])

    distance = bch.ResultVar("m", doc="Response distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        return super().__call__()"""

_LATENCY_PROFILE_CODE = """\
import math


class LatencyProfile(bch.ParametrizedSweep):
    \"\"\"Latency as a function of load.\"\"\"

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Latency distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.load) + 0.5
        return super().__call__()"""

_LATENCY_NOISY_PROFILE_CODE = """\
import math
import random


class LatencyNoisyProfile(bch.ParametrizedSweep):
    \"\"\"Latency with noise as a function of load.\"\"\"

    load = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Latency distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.load) + 0.5
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)
        return super().__call__()"""

_THROUGHPUT_COMPARE_CODE = """\
class ThroughputCompare(bch.ParametrizedSweep):
    \"\"\"Throughput comparison across backends.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])

    distance = bch.ResultVar("m", doc="Throughput distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 5.4, "memcached": 4.1, "local": 8.7}
        self.distance = lookup[self.backend]
        return super().__call__()"""

_HEATMAP_DEMO_CODE = """\
import math


class HeatmapDemo(bch.ParametrizedSweep):
    \"\"\"2D heatmap of a trigonometric surface.\"\"\"

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Surface height")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        return super().__call__()"""

_SURFACE_DEMO_CODE = """\
import math


class SurfaceDemo(bch.ParametrizedSweep):
    \"\"\"3D surface of a trigonometric function.\"\"\"

    x = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Surface height")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)
        return super().__call__()"""

_JITTER_DEMO_CODE = """\
import random


class JitterDemo(bch.ParametrizedSweep):
    \"\"\"Jitter distribution across cache backends.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Jittered distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)
        return super().__call__()"""

_SCATTER_JITTER_DEMO_CODE = """\
import random


class ScatterJitterDemo(bch.ParametrizedSweep):
    \"\"\"Scatter with jitter across cache backends.\"\"\"

    backend = bch.StringSweep(["redis", "memcached", "local"])
    noise_scale = bch.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bch.ResultVar("m", doc="Jittered distance metric")

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)
        return super().__call__()"""

# ---------------------------------------------------------------------------
# Plot configuration table
# ---------------------------------------------------------------------------

PLOT_CONFIGS = {
    "bar": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_bar()",
        "input_vars": '["backend"]',
        "benchable_class": "CacheCompare",
        "class_code": _CACHE_COMPARE_CODE,
    },
    "line": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_line()",
        "input_vars": '["load"]',
        "benchable_class": "LatencyProfile",
        "class_code": _LATENCY_PROFILE_CODE,
    },
    "curve": {
        "float_dims": 1,
        "cat_dims": 0,
        "repeats": 5,
        "plot_call": "res.to_curve()",
        "input_vars": '["load"]',
        "benchable_class": "LatencyNoisyProfile",
        "class_code": _LATENCY_NOISY_PROFILE_CODE,
    },
    "scatter": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_scatter()",
        "input_vars": '["backend"]',
        "benchable_class": "ThroughputCompare",
        "class_code": _THROUGHPUT_COMPARE_CODE,
    },
    "heatmap": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_heatmap()",
        "input_vars": '["x", "y"]',
        "benchable_class": "HeatmapDemo",
        "class_code": _HEATMAP_DEMO_CODE,
    },
    "surface": {
        "float_dims": 2,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_surface()",
        "input_vars": '["x", "y"]',
        "benchable_class": "SurfaceDemo",
        "class_code": _SURFACE_DEMO_CODE,
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
        "input_vars": '["backend"]',
        "benchable_class": "JitterDemo",
        "class_code": _JITTER_DEMO_CODE,
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
        "input_vars": '["backend"]',
        "benchable_class": "ScatterJitterDemo",
        "class_code": _SCATTER_JITTER_DEMO_CODE,
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

        const_vars = "dict(noise_scale=0.15)" if cfg["repeats"] > 1 else None
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
            result_vars='["distance"]',
            const_vars=const_vars,
            post_sweep_line=cfg["plot_call"],
            extra_imports=extra_imports,
            run_kwargs=run_kwargs,
            class_code=cfg["class_code"],
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
