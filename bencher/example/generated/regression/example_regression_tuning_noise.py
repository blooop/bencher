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
        figsize=(5.0, 3.2),
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

    def benchmark(self):
        baseline = 100.0
        hist = np.array([baseline + random.gauss(0, self.noise_sigma) for _ in range(20)])
        current = np.array(
            [baseline + _REGRESSION_STEP + random.gauss(0, self.noise_sigma) for _ in range(5)]
        )
        pct = self.regression_percentage if self.regression_percentage > 0.0 else None
        result = detect_adaptive(
            "metric",
            hist,
            current,
            regression_mad=self._Z_THRESHOLD,
            direction=bn.OptDir.minimize,
            regression_percentage=pct,
        )
        self.detection_plot = _render_detection_png(hist, current, result)


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
