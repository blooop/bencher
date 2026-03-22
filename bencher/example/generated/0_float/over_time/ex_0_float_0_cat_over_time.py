"""Auto-generated example: 0 Float, 0 Categorical (over time)."""

from typing import Any

import random
import bencher as bn
from datetime import datetime, timedelta


class BaselineCheck(bn.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bn.ResultVar(units="ms", doc="Baseline latency")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.baseline = 42.0
        self.baseline += random.gauss(0, 0.1 * 5)
        self.baseline += self._time_offset * 10
        return super().__call__()


def example_0_float_0_cat_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """0 Float, 0 Categorical (over time)."""
    run_cfg = run_cfg or bn.BenchRunCfg()
    run_cfg.over_time = True
    benchable = BaselineCheck()
    bench = benchable.to_bench(run_cfg)
    _base_time = datetime(2000, 1, 1)
    for i, offset in enumerate([0.0, 0.5, 1.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        res = bench.plot_sweep(
            "over_time",
            input_vars=[],
            result_vars=["baseline"],
            run_cfg=run_cfg,
            time_src=_base_time + timedelta(seconds=i),
        )

    return bench


if __name__ == "__main__":
    bn.run(example_0_float_0_cat_over_time, level=4)
