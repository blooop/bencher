"""Auto-generated example: Adaptive detector — tuning drift."""

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


class DriftDetection(bn.ParametrizedSweep):
    """Gradual drift — parametrised by drift rate and z-threshold."""

    drift_rate = bn.FloatSweep(
        default=1.0,
        bounds=[0.0, 4.0],
        doc="Drift per time step",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 5.5],
        doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

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
        result = detect_regression(
            "metric",
            hist,
            current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
            historical_time_means=hist,
        )
        self.detection_plot = _render_detection_png(hist, current, result)


def example_regression_tuning_drift(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning drift."""
    bench = DriftDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["drift_rate", "z_threshold"],
        result_vars=["detection_plot"],
        description="A linear drift is added to the history (fixed noise σ=5). With 20 time points, the total drift equals drift_rate × 20 and the current run continues the trend.  The drift test (Theil–Sen slope + Mann–Kendall trend guard) fires when the accumulated drift outweighs the detrended noise.  Low drift rates or high z_thresholds allow the trend to pass unnoticed.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_drift, level=3)
