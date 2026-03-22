"""Auto-generated example: Aggregate Over Time — 2D sweep to scalar curve with error bounds."""

from typing import Any

import math
import bencher as bn
from datetime import datetime, timedelta


class ThermalPlate(bn.ParametrizedSweep):
    """Measures temperature across a 2D plate that cools over time.

    A 2D sweep (x, y) is run at each time snapshot. Both dimensions are
    then collapsed via aggregate=True, producing a single mean +/- std per
    time point. The curve shows how the plate-wide average temperature
    decays, with error bounds from the spatial variation across the grid.
    """

    x = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Horizontal position on plate")
    y = bn.FloatSweep(default=0.5, bounds=[0.0, 1.0], doc="Vertical position on plate")

    temperature = bn.ResultVar(units="C", doc="Measured temperature")

    _time_offset = 0.0  # set externally per snapshot

    def __call__(self, **kwargs: Any) -> Any:
        self.update_params_from_kwargs(**kwargs)
        # Hot spot at centre, decaying over time
        self.temperature = (
            100
            * math.sin(math.pi * self.x)
            * math.sin(math.pi * self.y)
            * math.exp(-0.3 * self._time_offset)
            + 20
        )
        return super().__call__()


def example_advanced_agg_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Aggregate Over Time — 2D sweep to scalar curve with error bounds."""
    run_cfg = bn.BenchRunCfg.with_defaults(run_cfg)
    run_cfg.over_time = True

    benchable = ThermalPlate()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    time_offsets = [0.0, 1.0, 2.0, 3.0, 4.0]
    for i, offset in enumerate(time_offsets):
        benchable._time_offset = offset
        run_cfg.clear_cache = True
        run_cfg.clear_history = i == 0
        run_cfg.auto_plot = i == len(time_offsets) - 1
        bench.plot_sweep(
            "thermal_plate",
            input_vars=["x", "y"],
            result_vars=["temperature"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            aggregate=True,
        )

    return bench


if __name__ == "__main__":
    bn.run(example_advanced_agg_over_time, level=4)
