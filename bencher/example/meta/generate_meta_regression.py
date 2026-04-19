"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks, and 2-D tuning grids that show
where the unified detector fires or stays quiet.
"""

from dataclasses import dataclass

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"


# ---------------------------------------------------------------------------
# Tuning examples — 2-D sweeps (effect × z_threshold) with ResultReference
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TuningSpec:
    """Config for a 2D tuning example with holoviews ResultReference output.

    Each spec sweeps two ``FloatSweep`` inputs and produces a per-cell
    holoviews plot showing the synthesised time-series and the detection
    outcome.
    """

    classname: str
    class_code: str  # full class definition (+ optional module-level constants)
    input_vars: tuple[str, ...] = ("noise_sigma", "z_threshold")
    description: str = ""


# Shared helper emitted at the top of every tuning example file — renders the
# regression as a PNG via matplotlib so the diagnostic is self-contained and
# suitable for a GitHub PR comment.
_TUNING_RENDER_FN = '''\
def _render_detection_png(hist, current, result):
    """Render the detector outcome as a PNG and return its path."""
    return render_regression_png(
        result, hist, current,
        path=bn.gen_image_path(f"regression_{result.method}"),
        figsize=(5.0, 3.2), dpi=100,
    )'''


_TUNING: dict[str, TuningSpec] = {
    # ---- 1. Step regression parametrised by magnitude ----------------------
    "tuning_step": TuningSpec(
        classname="StepDetection",
        input_vars=("regression_magnitude", "z_threshold"),
        description=(
            "A step regression of variable magnitude is injected (fixed noise σ=10). "
            "Each cell shows the synthesised 20-point history and the current run. "
            "When the regression magnitude is large relative to noise and the "
            "z_threshold is low the detector fires; when the magnitude shrinks or "
            "the threshold rises it stays quiet.  The boundary reveals the minimum "
            "detectable effect for each threshold setting."
        ),
        class_code="""\
class StepDetection(bn.ParametrizedSweep):
    \"\"\"Step regression — parametrised by magnitude and z-threshold.\"\"\"

    regression_magnitude = bn.FloatSweep(
        default=25.0, bounds=[0.0, 60.0], doc="Regression step size",
    )
    z_threshold = bn.FloatSweep(
        default=3.5, bounds=[1.5, 5.5], doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _NOISE = 10.0

    def benchmark(self):
        baseline = 100.0
        hist = np.array(
            [baseline + random.gauss(0, self._NOISE) for _ in range(20)]
        )
        current = np.array(
            [baseline + self.regression_magnitude + random.gauss(0, self._NOISE)
             for _ in range(5)]
        )
        result = detect_regression(
            "metric", hist, current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
        )
        self.detection_plot = _render_detection_png(hist, current, result)""",
    ),
    # ---- 2. Gradual drift parametrised by drift rate -----------------------
    "tuning_drift": TuningSpec(
        classname="DriftDetection",
        input_vars=("drift_rate", "z_threshold"),
        description=(
            "A linear drift is added to the history (fixed noise σ=5). "
            "With 20 time points, the total drift equals drift_rate × 20 "
            "and the current run continues the trend.  The drift test "
            "(Theil–Sen slope + Mann–Kendall trend guard) fires when "
            "the accumulated drift outweighs the detrended noise.  Low "
            "drift rates or high z_thresholds allow the trend to pass "
            "unnoticed."
        ),
        class_code="""\
class DriftDetection(bn.ParametrizedSweep):
    \"\"\"Gradual drift — parametrised by drift rate and z-threshold.\"\"\"

    drift_rate = bn.FloatSweep(
        default=1.0, bounds=[0.0, 4.0], doc="Drift per time step",
    )
    z_threshold = bn.FloatSweep(
        default=3.5, bounds=[1.5, 5.5], doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _NOISE = 5.0
    _N_HIST = 20

    def benchmark(self):
        baseline = 100.0
        hist = np.array(
            [baseline + self.drift_rate * i + random.gauss(0, self._NOISE)
             for i in range(self._N_HIST)]
        )
        current = np.array(
            [baseline + self.drift_rate * self._N_HIST
             + random.gauss(0, self._NOISE)
             for _ in range(5)]
        )
        result = detect_regression(
            "metric", hist, current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
            historical_time_means=hist,
        )
        self.detection_plot = _render_detection_png(hist, current, result)""",
    ),
    # ---- 3. Noise robustness (fixed regression, varying noise) -------------
    "tuning_noise": TuningSpec(
        classname="NoiseRobustness",
        input_vars=("noise_sigma", "z_threshold"),
        description=(
            "A fixed +25 step regression is present, but the noise level varies. "
            "At low noise the regression is obvious and every threshold catches it; "
            "at high noise the signal is buried.  The detection boundary follows "
            "noise_sigma ≈ 25 / z_threshold — above the curve the regression is "
            "masked.  This helps users understand how metric variance affects the "
            "minimum z_threshold needed to catch a real regression."
        ),
        class_code="""\
_REGRESSION_STEP = 25.0


class NoiseRobustness(bn.ParametrizedSweep):
    \"\"\"Fixed 25-unit regression with varying noise — tests noise robustness.\"\"\"

    noise_sigma = bn.FloatSweep(
        default=10.0, bounds=[0.0, 40.0], doc="Noise standard deviation",
    )
    z_threshold = bn.FloatSweep(
        default=3.5, bounds=[1.5, 5.5], doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    def benchmark(self):
        baseline = 100.0
        hist = np.array(
            [baseline + random.gauss(0, self.noise_sigma) for _ in range(20)]
        )
        current = np.array(
            [baseline + _REGRESSION_STEP + random.gauss(0, self.noise_sigma)
             for _ in range(5)]
        )
        result = detect_regression(
            "metric", hist, current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
        )
        self.detection_plot = _render_detection_png(hist, current, result)""",
    ),
}


# ---------------------------------------------------------------------------
# Example list & generator class
# ---------------------------------------------------------------------------

REGRESSION_EXAMPLES = [
    "regression_over_time",
    *[f"regression_{tuning}" for tuning in _TUNING],
]


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bn.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def benchmark(self):
        if self.example == "regression_over_time":
            self._generate_over_time()
            return

        for tuning, spec in _TUNING.items():
            if self.example == f"regression_{tuning}":
                self._generate_tuning(tuning, spec)
                return

    def _generate_over_time(self):
        """End-to-end over_time example that trips the detector."""
        imports = "from datetime import datetime, timedelta\n\nimport bencher as bn"
        class_code = '''\
class ServerBenchmark(bn.ParametrizedSweep):
    """A server benchmark whose response time degrades over successive releases."""

    connections = bn.FloatSweep(default=50, bounds=[10, 200], doc="Concurrent clients")
    payload_kb = bn.FloatSweep(default=64, bounds=[1, 256], doc="Request payload size in KB")

    response_time = bn.ResultFloat(units="ms", direction=bn.OptDir.minimize)
    throughput = bn.ResultFloat(units="req/s", direction=bn.OptDir.maximize)

    _time_offset = 0.0  # set externally per snapshot

    def benchmark(self):
        base_rt = 5.0 + 0.15 * self.connections + 0.08 * self.payload_kb
        leak = 1.0 + self._time_offset * 0.12  # memory leak grows per release
        self.response_time = base_rt * leak
        self.throughput = 1000.0 / self.response_time'''
        body = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=2)
run_cfg.regression_detection = True
run_cfg.regression_fail = False

benchable = ServerBenchmark()
bench = benchable.to_bench(run_cfg)

# Simulate 7 server releases: stable at first, then a memory leak kicks in
releases = [0.0, 0.1, 0.0, 0.5, 1.5, 3.0, 5.0]

base_time = datetime(2024, 1, 1)
for i, offset in enumerate(releases):
    benchable._time_offset = offset
    run_cfg.clear_cache = True
    run_cfg.clear_history = i == 0
    run_cfg.auto_plot = i == len(releases) - 1
    bench.plot_sweep(
        "regression_detection",
        input_vars=["connections", "payload_kb"],
        result_vars=["response_time", "throughput"],
        run_cfg=run_cfg,
        time_src=base_time + timedelta(seconds=i),
        aggregate=True,
    )
"""
        self.generate_example(
            title="Regression detection — over time",
            output_dir=OUTPUT_DIR,
            filename="example_regression_over_time",
            function_name="example_regression_over_time",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"over_time": True},
        )

    def _generate_tuning(self, tuning: str, spec: TuningSpec) -> None:
        """Emit a 2D tuning example with holoviews ResultReference output."""
        title = f"Adaptive detector — {tuning.replace('_', ' ')}"

        imports = (
            "import random\n\n"
            "import numpy as np\n\n"
            "import bencher as bn\n"
            "from bencher.regression import detect_regression, render_regression_png"
        )

        class_code = _TUNING_RENDER_FN + "\n\n\n" + spec.class_code
        input_vars_str = repr(list(spec.input_vars))

        body = (
            f"bench = {spec.classname}().to_bench(run_cfg)\n"
            "bench.plot_sweep(\n"
            f"    input_vars={input_vars_str},\n"
            '    result_vars=["detection_plot"],\n'
            f"    description={spec.description!r},\n"
            ")\n"
        )

        filename = f"example_regression_{tuning}"
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=filename,
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"level": 3},
        )


def example_meta_regression(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    bench = MetaRegression().to_bench(run_cfg)

    bench.plot_sweep(
        title="Regression Detection",
        input_vars=[bn.sweep("example", REGRESSION_EXAMPLES)],
    )

    return bench


if __name__ == "__main__":
    bn.run(example_meta_regression)
