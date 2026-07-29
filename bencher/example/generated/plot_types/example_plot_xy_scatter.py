"""Auto-generated example: Plot Type: Xy Scatter."""

import random

import pandas as pd

import bencher as bn
from bencher.results.holoview_results.xy_scatter_result import XYScatterResult


class TouchCloud(bn.ParametrizedSweep):
    """Where a repeated motion lands: one row per touch, both axes measured."""

    spread = bn.FloatSweep(default=0.5, bounds=[0.1, 1.0], doc="Positioning noise")

    touches = bn.ResultDataSet(doc="Landing points, one row per touch")

    def benchmark(self):
        rng = random.Random(0)
        self.touches = bn.ResultDataSet(
            pd.DataFrame(
                [
                    {
                        "touch": i,
                        "dx_mm": rng.gauss(0.0, self.spread),
                        "dy_mm": rng.gauss(0.0, self.spread),
                    }
                    for i in range(60)
                ]
            )
        )


def example_plot_xy_scatter(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Xy Scatter."""
    bench = TouchCloud().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["spread"], result_vars=["touches"])
    bench.report.append(res.to(XYScatterResult, x="dx_mm", y="dy_mm", color="touch", data_aspect=1))

    return bench


if __name__ == "__main__":
    bn.run(example_plot_xy_scatter, subsampling_divisions=3)
