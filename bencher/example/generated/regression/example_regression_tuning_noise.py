"""Auto-generated example: Adaptive detector — tuning noise."""

import random

import numpy as np

import bencher as bn
from bencher.regression import detect_regression, render_regression_png


def _render_detection_png(hist, current, result):
    """Render the detector outcome as a PNG and return its path."""
    return render_regression_png(
        result,
        hist,
        current,
        path=bn.gen_image_path(f"regression_{result.method}"),
        figsize=(5.0, 3.2),
        dpi=100,
    )


_REGRESSION_STEP = 25.0


class NoiseRobustness(bn.ParametrizedSweep):
    """Fixed 25-unit regression with varying noise — tests noise robustness."""

    noise_sigma = bn.FloatSweep(
        default=10.0,
        bounds=[0.0, 40.0],
        doc="Noise standard deviation",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 5.5],
        doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    def benchmark(self):
        baseline = 100.0
        hist = np.array([baseline + random.gauss(0, self.noise_sigma) for _ in range(20)])
        current = np.array(
            [baseline + _REGRESSION_STEP + random.gauss(0, self.noise_sigma) for _ in range(5)]
        )
        result = detect_regression(
            "metric",
            hist,
            current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
        )
        self.detection_plot = _render_detection_png(hist, current, result)


def example_regression_tuning_noise(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning noise."""
    bench = NoiseRobustness().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["noise_sigma", "z_threshold"],
        result_vars=["detection_plot"],
        description="A fixed +25 step regression is present, but the noise level varies. At low noise the regression is obvious and every threshold catches it; at high noise the signal is buried.  The detection boundary follows noise_sigma ≈ 25 / z_threshold — above the curve the regression is masked.  This helps users understand how metric variance affects the minimum z_threshold needed to catch a real regression.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_noise, level=3)
