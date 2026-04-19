"""Auto-generated example: Regression detector — tuning step."""

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


class StepDetection(bn.ParametrizedSweep):
    """Step regression — parametrised by magnitude and z-threshold."""

    regression_magnitude = bn.FloatSweep(
        default=25.0,
        bounds=[0.0, 60.0],
        doc="Regression step size",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.5, 5.5],
        doc="Detector z-threshold",
    )

    detection_plot = bn.ResultImage(doc="Regression diagnostic PNG")

    _NOISE = 10.0

    def benchmark(self):
        baseline = 100.0
        hist = np.array([baseline + random.gauss(0, self._NOISE) for _ in range(20)])
        current = np.array(
            [baseline + self.regression_magnitude + random.gauss(0, self._NOISE) for _ in range(5)]
        )
        result = detect_regression(
            "metric",
            hist,
            current,
            z_threshold=self.z_threshold,
            direction=bn.OptDir.minimize,
        )
        self.detection_plot = _render_detection_png(hist, current, result)


def example_regression_tuning_step(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression detector — tuning step."""
    bench = StepDetection().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["regression_magnitude", "z_threshold"],
        result_vars=["detection_plot"],
        description="A step regression of variable magnitude is injected (fixed noise σ=10). Each cell shows the synthesised 20-point history and the current run. When the regression magnitude is large relative to noise and the z_threshold is low the detector fires; when the magnitude shrinks or the threshold rises it stays quiet.  The boundary reveals the minimum detectable effect for each threshold setting.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_step, level=3)
