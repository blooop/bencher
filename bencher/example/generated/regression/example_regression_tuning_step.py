"""Auto-generated example: Adaptive detector — tuning step."""

import random

import holoviews as hv
import numpy as np

import bencher as bn
from bencher.regression import detect_adaptive

_MAD_TO_SIGMA = 1.4826


def _render_detection_plot(hist, current_mean, regressed, z_threshold):
    """Build a holoviews overlay showing the time-series and detection outcome."""
    median = float(np.median(hist))
    mad_sigma = _MAD_TO_SIGMA * float(np.median(np.abs(hist - median)))
    noise = max(mad_sigma, 1e-6 * abs(median), 1e-12)

    n = len(hist)
    hist_curve = hv.Curve(list(enumerate(hist)), "Step", "Value").opts(
        color="#1f77b4",
        line_width=1.5,
    )
    baseline_line = hv.HLine(median).opts(color="gray", line_dash="dashed", line_width=1)
    band = hv.HSpan(
        median - z_threshold * noise,
        median + z_threshold * noise,
    ).opts(color="green", alpha=0.1)

    marker_color = "#d62728" if regressed else "#2ca02c"
    current_pt = hv.Scatter([(n, current_mean)], "Step", "Value").opts(
        color=marker_color,
        size=10,
    )

    z = abs(current_mean - median) / noise
    tag = "REGRESSED" if regressed else "OK"

    return (band * baseline_line * hist_curve * current_pt).opts(
        title=f"{tag}  z={z:.1f}",
        width=300,
        height=200,
    )


class AdaptiveStepDetection(bn.ParametrizedSweep):
    """Step regression — parametrised by magnitude and z-threshold."""

    regression_magnitude = bn.FloatSweep(
        default=25.0,
        bounds=[0.0, 60.0],
        doc="Regression step size",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 6.0],
        doc="Adaptive z-threshold",
    )

    detection_plot = bn.ResultReference(units="plot")

    _NOISE = 10.0

    def benchmark(self):
        baseline = 100.0
        hist = np.array([baseline + random.gauss(0, self._NOISE) for _ in range(20)])
        current = np.array(
            [baseline + self.regression_magnitude + random.gauss(0, self._NOISE) for _ in range(5)]
        )
        result = detect_adaptive(
            "metric",
            hist,
            current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
        )
        self.detection_plot = bn.ResultReference()
        self.detection_plot.obj = _render_detection_plot(
            hist,
            float(np.mean(current)),
            result.regressed,
            self.z_threshold,
        )


def example_regression_tuning_step(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning step."""
    bench = AdaptiveStepDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["regression_magnitude", "z_threshold"],
        result_vars=["detection_plot"],
        description="A step regression of variable magnitude is injected (fixed noise σ=10). Each cell shows the synthesised 20-point history and the current run. When the regression magnitude is large relative to noise and the z_threshold is low the detector fires; when the magnitude shrinks or the threshold rises it stays quiet.  The boundary reveals the minimum detectable effect for each threshold setting.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_step, level=3)
