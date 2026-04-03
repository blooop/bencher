"""Meta-generator: Explicit Plot Conversions.

Shows ``res.to_<plot_type>()`` for each plot type with appropriate data.
Each generated example is fully self-contained with an inline class definition.
"""

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "plot_types"

# ---------------------------------------------------------------------------
# Inline class code for each plot type
# ---------------------------------------------------------------------------

_DEFAULT_CLASS = "BenchableObject"
_DEFAULT_MODULE = "bencher.example.meta.example_meta"
_BENCHABLE_MODULE = "bencher.example.meta.benchable_objects"

_CACHE_COMPARE_CODE = """\
class CacheCompare(bn.ParametrizedSweep):
    \"\"\"Compare response distance across cache backends.\"\"\"

    backend = bn.StringSweep(["redis", "memcached", "local"])

    distance = bn.ResultFloat("m", doc="Response distance metric")

    def benchmark(self):
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]"""

_LATENCY_PROFILE_CODE = """\
import math


class LatencyProfile(bn.ParametrizedSweep):
    \"\"\"Latency as a function of load.\"\"\"

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Latency distance metric")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.load) + 0.5"""

_LATENCY_NOISY_PROFILE_CODE = """\
import math
import random


class LatencyNoisyProfile(bn.ParametrizedSweep):
    \"\"\"Latency with noise as a function of load.\"\"\"

    load = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Latency distance metric")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.load) + 0.5
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)"""

_THROUGHPUT_COMPARE_CODE = """\
class ThroughputCompare(bn.ParametrizedSweep):
    \"\"\"Throughput comparison across backends.\"\"\"

    backend = bn.StringSweep(["redis", "memcached", "local"])

    distance = bn.ResultFloat("m", doc="Throughput distance metric")

    def benchmark(self):
        lookup = {"redis": 5.4, "memcached": 4.1, "local": 8.7}
        self.distance = lookup[self.backend]"""

_HEATMAP_DEMO_CODE = """\
import math


class HeatmapDemo(bn.ParametrizedSweep):
    \"\"\"2D heatmap of a trigonometric surface.\"\"\"

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Surface height")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)"""

_SURFACE_DEMO_CODE = """\
import math


class SurfaceDemo(bn.ParametrizedSweep):
    \"\"\"3D surface of a trigonometric function.\"\"\"

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Surface height")

    def benchmark(self):
        self.distance = math.sin(math.pi * self.x) * math.cos(math.pi * self.y)"""

_JITTER_DEMO_CODE = """\
import random


class JitterDemo(bn.ParametrizedSweep):
    \"\"\"Jitter distribution across cache backends.\"\"\"

    backend = bn.StringSweep(["redis", "memcached", "local"])
    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Jittered distance metric")

    def benchmark(self):
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)"""

_SCATTER_JITTER_DEMO_CODE = """\
import random


class ScatterJitterDemo(bn.ParametrizedSweep):
    \"\"\"Scatter with jitter across cache backends.\"\"\"

    backend = bn.StringSweep(["redis", "memcached", "local"])
    noise_scale = bn.FloatSweep(default=0.0, bounds=[0.0, 1.0])

    distance = bn.ResultFloat("m", doc="Jittered distance metric")

    def benchmark(self):
        lookup = {"redis": 1.2, "memcached": 0.9, "local": 0.3}
        self.distance = lookup[self.backend]
        if self.noise_scale > 0:
            self.distance += random.gauss(0, self.noise_scale)"""

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
    "volume": {
        "float_dims": 3,
        "cat_dims": 0,
        "repeats": 1,
        "plot_call": "res.to_volume()",
        "input_vars": '["float1", "float2", "float3"]',
    },
    "image": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_panes()",
        "input_vars": '["sides"]',
        "benchable_class": "BenchableImageResult",
        "benchable_module": _BENCHABLE_MODULE,
        "result_vars": '["polygon"]',
    },
    "video": {
        "float_dims": 0,
        "cat_dims": 1,
        "repeats": 1,
        "plot_call": "res.to_panes()",
        "input_vars": '["sides"]',
        "benchable_class": "BenchableVideoResult",
        "benchable_module": _BENCHABLE_MODULE,
        "result_vars": '["animation"]',
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

    plot_type = bn.StringSweep(PLOT_NAMES, doc="Plot type to demonstrate")

    def benchmark(self):
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

        # Use inline class_code when available, otherwise import from module
        has_inline = "class_code" in cfg
        benchable_module = None if has_inline else cfg.get("benchable_module", _DEFAULT_MODULE)

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=cfg.get("benchable_class", _DEFAULT_CLASS),
            benchable_module=benchable_module,
            input_vars=cfg["input_vars"],
            result_vars=cfg.get("result_vars", '["distance"]'),
            const_vars=const_vars,
            post_sweep_line=cfg["plot_call"],
            extra_imports=extra_imports,
            run_kwargs=run_kwargs,
            class_code=cfg.get("class_code"),
        )


def example_meta_plot_types(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaPlotTypes().to_bench(run_cfg)

    bench.plot_sweep(
        title="Plot Types",
        input_vars=[bn.sweep("plot_type", PLOT_NAMES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_plot_types)
