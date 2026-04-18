"""Meta-generator: Regression detection examples.

Demonstrates how to use regression detection to catch performance
regressions in over-time benchmarks, and how to tune each method's
threshold against the amount of regression that needs detecting.
"""

from dataclasses import dataclass

import bencher as bn
from bencher.example.meta.meta_generator_base import MetaGeneratorBase

OUTPUT_DIR = "regression"


@dataclass(frozen=True)
class TuningSpec:
    """Per-method config for a 2-D ``regression_magnitude × threshold`` sweep.

    Each method has its own threshold parameter with its own units and typical
    range. Kept in one place so the template below can render a self-contained
    example file per method.
    """

    classname: str
    threshold_attr: str
    threshold_default: float
    threshold_lo: float
    threshold_hi: float
    threshold_doc: str
    detector_import: str
    detector_call: str


_TUNING_METHODS: dict[str, TuningSpec] = {
    "percentage": TuningSpec(
        classname="PercentageTuning",
        threshold_attr="percentage_threshold",
        threshold_default=5.0,
        threshold_lo=1.0,
        threshold_hi=20.0,
        threshold_doc="percent change vs baseline mean",
        detector_import="from bencher.regression import detect_percentage",
        detector_call=(
            'result = detect_percentage("metric", hist_samples, current, '
            "threshold_percent=self.percentage_threshold, "
            "direction=bn.OptDir.minimize)"
        ),
    ),
    "iqr": TuningSpec(
        classname="IqrTuning",
        threshold_attr="iqr_scale",
        threshold_default=1.5,
        threshold_lo=0.5,
        threshold_hi=3.5,
        threshold_doc="IQR multiplier for outlier bounds",
        detector_import="from bencher.regression import detect_iqr",
        detector_call=(
            'result = detect_iqr("metric", hist_time_means, current, '
            "iqr_scale=self.iqr_scale, direction=bn.OptDir.minimize)"
        ),
    ),
    "ttest": TuningSpec(
        classname="TtestTuning",
        threshold_attr="alpha",
        threshold_default=0.05,
        threshold_lo=0.01,
        threshold_hi=0.20,
        threshold_doc="significance level for Welch's t-test",
        detector_import="from bencher.regression import detect_ttest",
        detector_call=(
            'result = detect_ttest("metric", hist_samples, current, '
            "alpha=self.alpha, direction=bn.OptDir.minimize)"
        ),
    ),
    "adaptive": TuningSpec(
        classname="AdaptiveTuning",
        threshold_attr="z_threshold",
        threshold_default=3.5,
        threshold_lo=1.0,
        threshold_hi=6.0,
        threshold_doc="robust z-score threshold in MAD-sigma units",
        detector_import="from bencher.regression import detect_adaptive",
        detector_call=(
            'result = detect_adaptive("metric", hist_time_means, current, '
            "z_threshold=self.z_threshold, direction=bn.OptDir.minimize, "
            "historical_samples=hist_samples)"
        ),
    ),
}


_TUNING_CLASS_TEMPLATE = '''\
class {classname}(bn.ParametrizedSweep):
    """Sweep ``regression_magnitude`` × ``{threshold_attr}`` for ``{method}``.

    The ``regression_magnitude=0`` column shows the false-positive rate at
    each threshold. Non-zero columns show detection power as the regression
    grows. Noise level is held fixed so the heatmap stays 2-D.
    """

    regression_magnitude = bn.FloatSweep(
        default=0.0,
        bounds=[0.0, 40.0],
        samples=6,
        doc="Step added to the current run in units of baseline mean "
        "(0 = no regression, ~40% = large regression).",
    )
    {threshold_attr} = bn.FloatSweep(
        default={threshold_default},
        bounds=[{threshold_lo}, {threshold_hi}],
        samples=6,
        doc="Detector threshold — {threshold_doc}.",
    )

    detection_rate = bn.ResultFloat(
        units="probability",
        direction=bn.OptDir.none,
        doc="Fraction of trials where the detector flagged a regression.",
    )

    # Fixed signal parameters — kept off the sweep so the result is 2-D.
    _baseline = 100.0
    _noise_sigma = 5.0            # per-sample noise (~5% of baseline)
    _n_history = 15               # historical releases
    _n_repeats_hist = 3           # samples per release
    _n_current = 3                # samples in the current run
    _n_trials = 40                # independent trials for rate estimation

    def benchmark(self):
        import numpy as np

        {detector_import}

        hits = 0
        for trial in range(self._n_trials):
            seed = (
                trial * 1_000_003
                + int(self.regression_magnitude * 997)
                + int(self.{threshold_attr} * 101)
            )
            rng = np.random.default_rng(seed & 0xFFFFFFFF)
            hist_samples = self._baseline + rng.normal(
                0.0,
                self._noise_sigma,
                self._n_history * self._n_repeats_hist,
            )
            hist_time_means = hist_samples.reshape(
                self._n_history, self._n_repeats_hist
            ).mean(axis=1)
            current = (
                self._baseline
                + self.regression_magnitude
                + rng.normal(0.0, self._noise_sigma, self._n_current)
            )
            {detector_call}
            if result.regressed:
                hits += 1
        self.detection_rate = hits / self._n_trials
'''


_TUNING_BODY_TEMPLATE = """\
run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
bench = {classname}().to_bench(run_cfg)
bench.plot_sweep(
    "Regression detection tuning — {method}",
    input_vars=["regression_magnitude", "{threshold_attr}"],
    result_vars=["detection_rate"],
    run_cfg=run_cfg,
)
"""


REGRESSION_EXAMPLES = [
    "regression_percentage",
    *[f"regression_tuning_{method}" for method in _TUNING_METHODS],
]


def _render_tuning_class(method: str, spec: TuningSpec) -> str:
    return _TUNING_CLASS_TEMPLATE.format(
        classname=spec.classname,
        threshold_attr=spec.threshold_attr,
        threshold_default=spec.threshold_default,
        threshold_lo=spec.threshold_lo,
        threshold_hi=spec.threshold_hi,
        threshold_doc=spec.threshold_doc,
        detector_import=spec.detector_import,
        detector_call=spec.detector_call,
        method=method,
    ).rstrip("\n")


class MetaRegression(MetaGeneratorBase):
    """Generate Python examples demonstrating regression detection."""

    example = bn.StringSweep(REGRESSION_EXAMPLES, doc="Which regression example to generate")

    def benchmark(self):
        if self.example == "regression_percentage":
            self._generate_percentage_over_time()
            return

        for method, spec in _TUNING_METHODS.items():
            if self.example == f"regression_tuning_{method}":
                self._generate_tuning(method, spec)
                return

    def _generate_percentage_over_time(self):
        """End-to-end over_time example that trips the percentage detector."""
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
run_cfg.regression_method = "percentage"
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
            title="Regression detection — percentage threshold over time",
            output_dir=OUTPUT_DIR,
            filename="example_regression_percentage",
            function_name="example_regression_percentage",
            imports=imports,
            body=body,
            class_code=class_code,
            run_kwargs={"over_time": True},
        )

    def _generate_tuning(self, method: str, spec: TuningSpec) -> None:
        """Emit a 2-D tuning sweep example for a single detection method."""
        title = (
            f"Regression detection tuning — '{method}' method "
            f"(regression_magnitude × {spec.threshold_attr})"
        )
        imports = "import bencher as bn"
        class_code = _render_tuning_class(method, spec)
        body = _TUNING_BODY_TEMPLATE.format(
            classname=spec.classname,
            method=method,
            threshold_attr=spec.threshold_attr,
        )
        filename = f"example_regression_tuning_{method}"
        self.generate_example(
            title=title,
            output_dir=OUTPUT_DIR,
            filename=filename,
            function_name=filename,
            imports=imports,
            body=body,
            class_code=class_code,
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
