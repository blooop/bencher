"""Auto-generated example: Adaptive detector — tuning noise."""

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


_REGRESSION_STEP = 25.0


class AdaptiveNoiseRobustness(bn.ParametrizedSweep):
    """Fixed 25-unit regression with varying noise — tests noise robustness."""

    noise_sigma = bn.FloatSweep(
        default=10.0,
        bounds=[2.0, 40.0],
        doc="Noise standard deviation",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 6.0],
        doc="Adaptive z-threshold",
    )

    detection_plot = bn.ResultReference(units="plot")

    def benchmark(self):
        baseline = 100.0
        hist = np.array([baseline + random.gauss(0, self.noise_sigma) for _ in range(20)])
        current = np.array(
            [baseline + _REGRESSION_STEP + random.gauss(0, self.noise_sigma) for _ in range(5)]
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


def example_regression_tuning_noise(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning noise."""
    bench = AdaptiveNoiseRobustness().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["noise_sigma", "z_threshold"],
        result_vars=["detection_plot"],
        description="A fixed +25 step regression is present, but the noise level varies. At low noise the regression is obvious and every threshold catches it; at high noise the signal is buried.  The detection boundary follows noise_sigma ≈ 25 / z_threshold — above the curve the regression is masked.  This helps users understand how metric variance affects the minimum z_threshold needed to catch a real regression.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_noise, level=3)
