"""Auto-generated example: Adaptive detector — tuning drift."""

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


class AdaptiveDriftDetection(bn.ParametrizedSweep):
    """Gradual drift — parametrised by drift rate and z-threshold."""

    drift_rate = bn.FloatSweep(
        default=1.0,
        bounds=[0.0, 4.0],
        doc="Drift per time step",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 6.0],
        doc="Adaptive z-threshold",
    )

    detection_plot = bn.ResultReference(units="plot")

    _NOISE = 5.0
    _N_HIST = 20

    def benchmark(self):
        baseline = 100.0
        hist = np.array(
            [
                baseline + self.drift_rate * i + random.gauss(0, self._NOISE)
                for i in range(self._N_HIST)
            ]
        )
        current = np.array(
            [
                baseline + self.drift_rate * self._N_HIST + random.gauss(0, self._NOISE)
                for _ in range(5)
            ]
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


def example_regression_tuning_drift(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning drift."""
    bench = AdaptiveDriftDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["drift_rate", "z_threshold"],
        result_vars=["detection_plot"],
        description="A linear drift is added to the history (fixed noise σ=5). With 20 time points, the total drift equals drift_rate × 20 and the current run continues the trend.  The adaptive drift test (Theil–Sen slope + Mann–Kendall trend guard) fires when the accumulated drift outweighs the detrended noise.  Low drift rates or high z_thresholds allow the trend to pass unnoticed.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_drift, level=3)
