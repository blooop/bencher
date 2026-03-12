"""Auto-generated example: 0 Float, 0 Categorical."""

from typing import Any

import bencher as bch
import random
from datetime import datetime, timedelta


class BaselineCheck(bch.ParametrizedSweep):
    """Measures a fixed baseline metric with no swept parameters."""

    baseline = bch.ResultVar(units="ms", doc="Baseline latency")

    _time_offset = 0.0

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        self.baseline = 42.0
        self.baseline += random.gauss(0, 0.15 * 5)
        self.baseline += self._time_offset * 10
        return super().__call__()


def example_over_time_repeats_0_float_0_cat(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """0 Float, 0 Categorical."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True
    run_cfg.repeats = 3
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
    bch.run(example_over_time_repeats_0_float_0_cat, level=4)
