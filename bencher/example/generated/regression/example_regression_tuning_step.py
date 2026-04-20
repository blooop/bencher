"""Auto-generated example: Adaptive detector — tuning step."""

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


class AdaptiveStepDetection(bn.ParametrizedSweep):
    """Step regression — parametrised by magnitude and z-threshold."""

    regression_magnitude = bn.FloatSweep(
        default=25.0, bounds=[0.0, 60.0], doc="Regression step size",
    )
    regression_mad = bn.FloatSweep(
        default=3.5, bounds=[1.5, 5.5], doc="Adaptive z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _NOISE = 10.0
    _N_HIST = 20
    _N_REPEATS = 5

    def benchmark(self):
        baseline = 100.0
        hist_2d = np.array([
            [baseline + random.gauss(0, self._NOISE) for _ in range(self._N_REPEATS)]
            for _ in range(self._N_HIST)
        ])
        hist_means = hist_2d.mean(axis=1)
        current = np.array(
            [baseline + self.regression_magnitude + random.gauss(0, self._NOISE)
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


def example_regression_tuning_step(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning step."""
    bench = AdaptiveStepDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=['regression_magnitude', 'regression_mad'],
        result_vars=["detection_plot"],
        description='A step regression of variable magnitude is injected (fixed noise σ=10). Each cell shows the synthesised 20-point history and the current run. When the regression magnitude is large relative to noise and the regression_mad is low the detector fires; when the magnitude shrinks or the threshold rises it stays quiet.  The boundary reveals the minimum detectable effect for each threshold setting.',
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_step, level=3)
