"""Auto-generated example: Adaptive detector — tuning noise."""

import random

import numpy as np

import bencher as bn
from bencher.regression import detect_adaptive, render_regression_png


def _render_detection_png(hist, current, result):
    """Render the adaptive-detector outcome as a PNG and return its path."""
    return render_regression_png(
        result,
        hist,
        current,
        path=bn.gen_image_path(f"regression_{result.method}"),
        figsize=(4.5, 3.2),
        dpi=100,
    )


_REGRESSION_STEP = 25.0


class AdaptiveNoiseRobustness(bn.ParametrizedSweep):
    """Fixed 25-unit regression with varying noise and regression_percentage."""

    noise_sigma = bn.FloatSweep(
        default=10.0,
        bounds=[0.0, 40.0],
        doc="Noise standard deviation (0.0 collapses MAD and leaves only the percentage band).",
    )
    regression_percentage = bn.FloatSweep(
        default=10.0,
        bounds=[0.0, 40.0],
        doc="Minimum percent change required to flag a regression (dual-band "
        "AND gate). 0.0 disables the percentage gate.",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _Z_THRESHOLD = 3.5
    _N_HIST = 20
    _N_REPEATS = 5

    def benchmark(self):
        baseline = 100.0
        hist_2d = np.array(
            [
                [baseline + random.gauss(0, self.noise_sigma) for _ in range(self._N_REPEATS)]
                for _ in range(self._N_HIST)
            ]
        )
        hist_means = hist_2d.mean(axis=1)
        current = np.array(
            [baseline + _REGRESSION_STEP + random.gauss(0, self.noise_sigma) for _ in range(5)]
        )
        pct = self.regression_percentage if self.regression_percentage > 0.0 else None
        result = detect_adaptive(
            "metric",
            hist_means,
            current,
            regression_mad=self._Z_THRESHOLD,
            direction=bn.OptDir.minimize,
            regression_percentage=pct,
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


def example_regression_tuning_noise(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Adaptive detector — tuning noise."""
    bench = AdaptiveNoiseRobustness().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["noise_sigma", "regression_percentage"],
        result_vars=["detection_plot"],
        description="A fixed +25 step regression is present, but the noise level varies. At low noise the regression is obvious and the MAD acceptance band is tight; at high noise the signal is buried and the MAD band is wide. The noise_sigma=0 row is the pathological case: MAD collapses to zero, the MAD band is a hairline, and only the percentage band is visible — that row shows the percentage acceptance band on its own. Increase regression_percentage in any row to see the percentage band expand and AND-gate the verdict.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_noise, level=3)
