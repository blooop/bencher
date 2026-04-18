"""Auto-generated example: Regression scenario — sudden drop."""

from datetime import datetime, timedelta
import random

import bencher as bn


class SuddenDropMetric(bn.ParametrizedSweep):
    """Metric jumps at step 15 — step regression expected."""

    metric_value = bn.ResultFloat(units="units", direction=bn.OptDir.minimize)

    _step = 0  # set externally per time point

    def benchmark(self):
        base = 100.0 if self._step < 15 else 130.0
        self.metric_value = base + random.gauss(0, 5.0)


def example_regression_sudden_drop(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Regression scenario — sudden drop."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg, repeats=3)
    run_cfg.regression_detection = True
    run_cfg.regression_method = "adaptive"
    run_cfg.regression_fail = False

    benchable = SuddenDropMetric()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    for i in range(20):
        benchable._step = i
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == 20 - 1
        bench.plot_sweep(
            "sudden_drop",
            input_vars=[],
            result_vars=["metric_value"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_regression_sudden_drop, over_time=True)
