"""Auto-generated example: Aggregate Over Time — curve with error bounds from swept dims."""

from typing import Any

import math
import bencher as bch
from datetime import datetime, timedelta


class ThermalSweep(bch.ParametrizedSweep):
    """Measures heat dissipation across sensor positions over time.

    When over_time=True and a float input is swept, aggregating over that
    input (via agg_over_dims) collapses it to mean +/- std at each time
    point. The std shows the spread across sensor positions.
    """

    position = bch.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Sensor position along rod")

    temperature = bch.ResultVar(units="C", doc="Measured temperature")

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        # Temperature varies along the rod and decays over time
        self.temperature = (
            80 * math.sin(math.pi * self.position) * math.exp(-0.3 * self._time_offset) + 20
        )
        return super().__call__()


def example_advanced_agg_over_time(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Aggregate Over Time — curve with error bounds from swept dims."""
    run_cfg = run_cfg or bch.BenchRunCfg()
    run_cfg.over_time = True

    benchable = ThermalSweep()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    for i, offset in enumerate([0.0, 1.0, 2.0, 3.0, 4.0]):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = False
        bench.plot_sweep(
            "thermal_sweep",
            input_vars=["position"],
            result_vars=["temperature"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
        )

    # Aggregate over position: produces mean +/- std at each time point
    res = bench.results[-1]
    bench.report.append(res.to(bch.CurveResult, agg_over_dims=["position"]))

    return bench


if __name__ == "__main__":
    bch.run(example_advanced_agg_over_time, level=4)
