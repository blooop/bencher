"""Auto-generated example: Plot Type: Xy Curve."""

import numpy as np
import pandas as pd

import bencher as bn
from bencher.results.holoview_results.xy_curve_result import XYCurveResult


class SettlingTrace(bn.ParametrizedSweep):
    """A whole collected trace per sample: the rows are the series, not the sweep."""

    damping = bn.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Damping ratio")

    trace = bn.ResultDataSet(doc="Measured and commanded position over time")

    def benchmark(self):
        t = np.linspace(0.0, 10.0, 120)
        settled = 1.0 - np.exp(-self.damping * t) * np.cos(3.0 * t)
        self.trace = bn.ResultDataSet(
            pd.DataFrame({"time_s": t, "measured_mm": settled, "commanded_mm": np.ones_like(t)})
        )


def example_plot_xy_curve(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Xy Curve."""
    bench = SettlingTrace().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["damping"], result_vars=["trace"])
    bench.report.append(
        res.to(XYCurveResult, x="time_s", y=["measured_mm", "commanded_mm"], ylabel="position [mm]")
    )

    return bench


if __name__ == "__main__":
    bn.run(example_plot_xy_curve, subsampling_divisions=3)
