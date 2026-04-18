"""Auto-generated example: Regression scenario — gradual drift."""

from datetime import datetime, timedelta
import random

import bencher as bn


class GradualDriftMetric(bn.ParametrizedSweep):
    """Metric drifts upward over time — drift regression expected."""

    metric_value = bn.ResultFloat(units="units", direction=bn.OptDir.minimize)

    _step = 0  # set externally per time point

    def benchmark(self):
        self.metric_value = 100.0 + 1.5 * self._step + random.gauss(0, 5.0)


def example_regression_gradual_drift(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression scenario — gradual drift."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)
    run_cfg.regression_detection = True
    run_cfg.regression_method = "adaptive"
    run_cfg.regression_fail = False

    benchable = GradualDriftMetric()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    for i in range(20):
        benchable._step = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == 20 - 1
        bench.plot_sweep(
            "gradual_drift",
            input_vars=[],
            result_vars=["metric_value"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_gradual_drift, over_time=True)
