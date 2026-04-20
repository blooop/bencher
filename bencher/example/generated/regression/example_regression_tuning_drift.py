"""Auto-generated example: Adaptive detector — tuning drift."""

import random

import numpy as np

import bencher as bn
from bencher.regression import detect_adaptive, render_regression_png

def _render_detection_png(hist, current, result):
    """Render the adaptive-detector outcome as a PNG and return its path."""
    return render_regression_png(
        result, hist, current,
        path=bn.gen_image_path(f"regression_{result.method}"),
        figsize=(4.5, 3.2), dpi=100,
    )


class AdaptiveDriftDetection(bn.ParametrizedSweep):
    """Gradual drift — parametrised by drift rate and z-threshold."""

    drift_rate = bn.FloatSweep(
        default=1.0, bounds=[0.0, 4.0], doc="Drift per time step",
    )
    regression_mad = bn.FloatSweep(
        default=3.5, bounds=[1.5, 5.5], doc="Adaptive z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _NOISE = 5.0
    _N_HIST = 20
    _N_REPEATS = 5

    def benchmark(self):
        baseline = 100.0
        hist_2d = np.array([
            [baseline + self.drift_rate * i + random.gauss(0, self._NOISE)
             for _ in range(self._N_REPEATS)]
            for i in range(self._N_HIST)
        ])
        hist_means = hist_2d.mean(axis=1)
        current = np.array(
            [baseline + self.drift_rate * self._N_HIST
             + random.gauss(0, self._NOISE)
             for _ in range(5)]
        )
        result = detect_adaptive(
            "metric", hist_means, current,
            regression_mad=self.regression_mad,
            direction=bn.OptDir.minimize,
            historical_samples=hist_2d.ravel(),
        )
        # git_time_event-style string labels for the x-axis; historical_all_x
        # stays numeric (integer positions aligned with the tick labels) so
        # the per-sample scatter still renders on the categorical axis.
        result.historical_x = np.array(
            [f"2024-01-{i + 1:02d} v{i:02d}" for i in range(self._N_HIST)]
        )
        result.current_x = f"2024-01-{self._N_HIST + 1:02d} v{self._N_HIST:02d}"
        result.historical_all = hist_2d.ravel()
        result.historical_all_x = np.repeat(np.arange(self._N_HIST), self._N_REPEATS)
        self.detection_plot = _render_detection_png(hist_means, current, result)


def example_regression_tuning_drift(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning drift."""
    bench = AdaptiveDriftDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=['drift_rate', 'regression_mad'],
        result_vars=["detection_plot"],
        description='A linear drift is added to the history (fixed noise σ=5). With 20 time points, the total drift equals drift_rate × 20 and the current run continues the trend.  The adaptive drift test (Theil–Sen slope + Mann–Kendall trend guard) fires when the accumulated drift outweighs the detrended noise.  Low drift rates or high regression_mads allow the trend to pass unnoticed.',
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_drift, level=3)
