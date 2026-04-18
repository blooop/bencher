"""Auto-generated example: Regression detection tuning — 'adaptive' method (regression_magnitude × z_threshold)."""

import bencher as bn


class AdaptiveTuning(bn.ParametrizedSweep):
    """Sweep ``regression_magnitude`` × ``z_threshold`` for ``adaptive``.

    The ``regression_magnitude=0`` column shows the false-positive rate at
    each threshold. Non-zero columns show detection power as the regression
    grows. Noise level is held fixed so the heatmap stays 2-D.
    """

    regression_magnitude = bn.FloatSweep(
        default=0.0,
        bounds=[0.0, 40.0],
        samples=6,
        doc="Step added to the current run in units of baseline mean "
        "(0 = no regression, ~40% = large regression).",
    )
    z_threshold = bn.FloatSweep(
        default=3.5,
        bounds=[1.0, 6.0],
        samples=6,
        doc="Detector threshold — robust z-score threshold in MAD-sigma units.",
    )

    detection_rate = bn.ResultFloat(
        units="probability",
        direction=bn.OptDir.none,
        doc="Fraction of trials where the detector flagged a regression.",
    )

    # Fixed signal parameters — kept off the sweep so the result is 2-D.
    _baseline = 100.0
    _noise_sigma = 5.0  # per-sample noise (~5% of baseline)
    _n_history = 15  # historical releases
    _n_repeats_hist = 3  # samples per release
    _n_current = 3  # samples in the current run
    _n_trials = 40  # independent trials for rate estimation

    def benchmark(self):
        import numpy as np

        from bencher.regression import detect_adaptive

        hits = 0
        for trial in range(self._n_trials):
            seed = (
                trial * 1_000_003
                + int(self.regression_magnitude * 997)
                + int(self.z_threshold * 101)
            )
            rng = np.random.default_rng(seed & 0xFFFFFFFF)
            hist_samples = self._baseline + rng.normal(
                0.0,
                self._noise_sigma,
                self._n_history * self._n_repeats_hist,
            )
            hist_time_means = hist_samples.reshape(self._n_history, self._n_repeats_hist).mean(
                axis=1
            )
            current = (
                self._baseline
                + self.regression_magnitude
                + rng.normal(0.0, self._noise_sigma, self._n_current)
            )
            result = detect_adaptive(
                "metric",
                hist_time_means,
                current,
                z_threshold=self.z_threshold,
                direction=bn.OptDir.minimize,
                historical_samples=hist_samples,
            )
            if result.regressed:
                hits += 1
        self.detection_rate = hits / self._n_trials


def example_regression_tuning_adaptive(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression detection tuning — 'adaptive' method (regression_magnitude × z_threshold)."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
    bench = AdaptiveTuning().to_bench(run_cfg)
    bench.plot_sweep(
        "Regression detection tuning — adaptive",
        input_vars=["regression_magnitude", "z_threshold"],
        result_vars=["detection_rate"],
        run_cfg=run_cfg,
    )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_tuning_adaptive)
