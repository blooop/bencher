"""Meta-generator: Explicit Plot Conversions.

Shows ``res.to_<plot_type>()`` for each plot type with appropriate data.
Each generated example is fully self-contained with an inline class definition.
"""

from dataclasses import dataclass

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

_TOUCH_CLOUD_CODE = """\
import random

import pandas as pd


class TouchCloud(bn.ParametrizedSweep):
    \"\"\"Where a repeated motion lands: one row per touch, both axes measured.\"\"\"

    spread = bn.FloatSweep(default=0.5, bounds=[0.1, 1.0], doc="Positioning noise")

    touches = bn.ResultDataSet(
        container=bn.xy_scatter(
            x="dx_mm",
            y="dy_mm",
            color="touch",
            data_aspect=1,
        ),
        doc="Landing points, one row per touch",
    )

    def benchmark(self):
        rng = random.Random(0)
        self.touches = bn.ResultDataSet(
            pd.DataFrame(
                [
                    {
                        "touch": i,
                        "dx_mm": rng.gauss(0.0, self.spread),
                        "dy_mm": rng.gauss(0.0, self.spread),
                    }
                    for i in range(60)
                ]
            )
        )"""

_SETTLING_TRACE_CODE = """\
import numpy as np
import pandas as pd


class SettlingTrace(bn.ParametrizedSweep):
    \"\"\"A whole collected trace per sample: the rows are the series, not the sweep.\"\"\"

    damping = bn.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Damping ratio")

    trace = bn.ResultDataSet(
        container=bn.xy_curve(
            x="time_s",
            y=["measured_mm", "commanded_mm"],
            ylabel="position [mm]",
        ),
        doc="Measured and commanded position over time",
    )

    def benchmark(self):
        t = np.linspace(0.0, 10.0, 120)
        settled = 1.0 - np.exp(-self.damping * t) * np.cos(3.0 * t)
        self.trace = bn.ResultDataSet(
            pd.DataFrame({"time_s": t, "measured_mm": settled, "commanded_mm": np.ones_like(t)})
        )"""

_LATENCY_SAMPLES_CODE = """\
import numpy as np
import pandas as pd


class LatencySamples(bn.ParametrizedSweep):
    \"\"\"Every request timed, not just the mean: the sample *is* the distribution.\"\"\"

    concurrency = bn.IntSweep(default=4, bounds=[1, 16], doc="Concurrent requests")

    latencies = bn.ResultDataSet(
        container=bn.xy_histogram(
            column=["latency_ms", "baseline_ms"],
            bins=40,
            xlabel="latency [ms]",
        ),
        doc="One row per request, measured and baseline",
    )

    def benchmark(self):
        rng = np.random.default_rng(self.concurrency)
        scale = 1.0 + 0.4 * self.concurrency
        self.latencies = bn.ResultDataSet(
            pd.DataFrame(
                {
                    "latency_ms": rng.gamma(3.0, scale, 4000),
                    "baseline_ms": rng.gamma(3.0, 1.4, 4000),
                }
            )
        )"""

_DENSE_CLOUD_CODE = """\
import numpy as np
import pandas as pd


class DenseCloud(bn.ParametrizedSweep):
    \"\"\"Too many points to read as markers, so the marks become counts.\"\"\"

    spread = bn.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Positioning noise")

    touches = bn.ResultDataSet(
        container=bn.xy_hexbin(
            x="dx_mm",
            y="dy_mm",
            gridsize=30,
            min_count=1,
            data_aspect=1,
        ),
        doc="Landing points, one row per touch",
    )

    def benchmark(self):
        rng = np.random.default_rng(0)
        self.touches = bn.ResultDataSet(
            pd.DataFrame(
                {
                    "dx_mm": rng.normal(0.0, self.spread, 20000),
                    "dy_mm": rng.normal(0.0, self.spread, 20000),
                }
            )
        )"""

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


@dataclass(frozen=True)
class PlotConfig:
    """One row of the plot-type table: what to generate, and from what.

    This was a bare ``dict[str, int | str | None]`` until plan 23 P12b. Every read of a
    numeric field then came back as the whole union, so ``cfg["repeats"] > 1`` was not a
    legal comparison -- and no reader could tell an optional field from a mandatory one
    except by finding a ``.get()`` somewhere. The defaults below are the ones the
    consumer used to spell as ``.get(key, fallback)``.
    """

    float_dims: int
    cat_dims: int
    repeats: int
    # None for the container-declaring examples, whose ResultDataSet renders itself and
    # so emit no post-sweep line. Four of the fifteen rows.
    plot_call: str | None
    input_vars: str
    benchable_class: str = _DEFAULT_CLASS
    result_vars: str = '["distance"]'
    # None = generate an import from `benchable_module` instead of inlining a class.
    class_code: str | None = None
    benchable_module: str = _DEFAULT_MODULE
    extra_import: str | None = None


PLOT_CONFIGS: dict[str, PlotConfig] = {
    "bar": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=1,
        plot_call="res.to_bar()",
        input_vars='["backend"]',
        benchable_class="CacheCompare",
        class_code=_CACHE_COMPARE_CODE,
    ),
    "line": PlotConfig(
        float_dims=1,
        cat_dims=0,
        repeats=1,
        plot_call="res.to_line()",
        input_vars='["load"]',
        benchable_class="LatencyProfile",
        class_code=_LATENCY_PROFILE_CODE,
    ),
    "curve": PlotConfig(
        float_dims=1,
        cat_dims=0,
        repeats=5,
        plot_call="res.to_curve()",
        input_vars='["load"]',
        benchable_class="LatencyNoisyProfile",
        class_code=_LATENCY_NOISY_PROFILE_CODE,
    ),
    "scatter": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=1,
        plot_call="res.to_scatter()",
        input_vars='["backend"]',
        benchable_class="ThroughputCompare",
        class_code=_THROUGHPUT_COMPARE_CODE,
    ),
    "heatmap": PlotConfig(
        float_dims=2,
        cat_dims=0,
        repeats=1,
        plot_call="res.to_heatmap()",
        input_vars='["x", "y"]',
        benchable_class="HeatmapDemo",
        class_code=_HEATMAP_DEMO_CODE,
    ),
    "surface": PlotConfig(
        float_dims=2,
        cat_dims=0,
        repeats=1,
        plot_call="res.to_surface()",
        input_vars='["x", "y"]',
        benchable_class="SurfaceDemo",
        class_code=_SURFACE_DEMO_CODE,
    ),
    "volume": PlotConfig(
        float_dims=3,
        cat_dims=0,
        repeats=1,
        plot_call="res.to_volume()",
        input_vars='["float1", "float2", "float3"]',
    ),
    "image": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=1,
        plot_call="res.to_panes()",
        input_vars='["sides"]',
        benchable_class="BenchableImageResult",
        benchable_module=_BENCHABLE_MODULE,
        result_vars='["polygon"]',
    ),
    "video": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=1,
        plot_call="res.to_panes()",
        input_vars='["sides"]',
        benchable_class="BenchableVideoResult",
        benchable_module=_BENCHABLE_MODULE,
        result_vars='["animation"]',
    ),
    "box_whisker": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=10,
        plot_call="res.to(BoxWhiskerResult)",
        extra_import="from bencher.results.holoview_results.distribution_result"
        ".box_whisker_result import BoxWhiskerResult",
        input_vars='["backend"]',
        benchable_class="JitterDemo",
        class_code=_JITTER_DEMO_CODE,
    ),
    "scatter_jitter": PlotConfig(
        float_dims=0,
        cat_dims=1,
        repeats=10,
        plot_call="res.to(ScatterJitterResult)",
        extra_import="from bencher.results.holoview_results.distribution_result"
        ".scatter_jitter_result import ScatterJitterResult",
        input_vars='["backend"]',
        benchable_class="ScatterJitterDemo",
        class_code=_SCATTER_JITTER_DEMO_CODE,
    ),
    "xy_scatter": PlotConfig(
        float_dims=1,
        cat_dims=0,
        repeats=1,
        plot_call=None,
        input_vars='["spread"]',
        result_vars='["touches"]',
        benchable_class="TouchCloud",
        class_code=_TOUCH_CLOUD_CODE,
    ),
    "xy_curve": PlotConfig(
        float_dims=1,
        cat_dims=0,
        repeats=1,
        plot_call=None,
        input_vars='["damping"]',
        result_vars='["trace"]',
        benchable_class="SettlingTrace",
        class_code=_SETTLING_TRACE_CODE,
    ),
    "xy_histogram": PlotConfig(
        float_dims=0,
        cat_dims=0,
        repeats=1,
        plot_call=None,
        input_vars='["concurrency"]',
        result_vars='["latencies"]',
        benchable_class="LatencySamples",
        class_code=_LATENCY_SAMPLES_CODE,
    ),
    "xy_hexbin": PlotConfig(
        float_dims=1,
        cat_dims=0,
        repeats=1,
        plot_call=None,
        input_vars='["spread"]',
        result_vars='["touches"]',
        benchable_class="DenseCloud",
        class_code=_DENSE_CLOUD_CODE,
    ),
}

PLOT_NAMES = list(PLOT_CONFIGS.keys())


class MetaPlotTypes(MetaGeneratorBase):
    """Generate Python examples demonstrating each plot type."""

    plot_type = bn.StringSweep(PLOT_NAMES, doc="Plot type to demonstrate")

    def benchmark(self):
        cfg = PLOT_CONFIGS[self.plot_type]
        function_name = f"example_plot_{self.plot_type}"
        filename = function_name
        title = f"Plot Type: {self.plot_type.replace('_', ' ').title()}"

        const_vars = '{"noise_scale": 0.15}' if cfg.repeats > 1 else None
        extra_imports = [cfg.extra_import] if cfg.extra_import else None

        sd = 2 if cfg.float_dims >= 2 else 3
        run_kwargs = {"subsampling_divisions": sd}
        if cfg.repeats > 1:
            run_kwargs["repeats"] = cfg.repeats

        # Use inline class_code when available, otherwise import from module
        benchable_module = None if cfg.class_code is not None else cfg.benchable_module

        self.generate_sweep_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=function_name,
            benchable_class=cfg.benchable_class,
            benchable_module=benchable_module,
            input_vars=cfg.input_vars,
            result_vars=cfg.result_vars,
            const_vars=const_vars,
            post_sweep_line=cfg.plot_call,
            extra_imports=extra_imports,
            run_kwargs=run_kwargs,
            class_code=cfg.class_code,
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
