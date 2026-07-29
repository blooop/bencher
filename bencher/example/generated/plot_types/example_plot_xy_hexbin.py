"""Auto-generated example: Plot Type: Xy Hexbin."""

import numpy as np
import pandas as pd

import bencher as bn
from bencher.results.holoview_results.xy_hexbin_result import XYHexbinResult


class DenseCloud(bn.ParametrizedSweep):
    """Too many points to read as markers, so the marks become counts."""

    spread = bn.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Positioning noise")

    touches = bn.ResultDataSet(doc="Landing points, one row per touch")

    def benchmark(self):
        rng = np.random.default_rng(0)
        self.touches = bn.ResultDataSet(
            pd.DataFrame(
                {
                    "dx_mm": rng.normal(0.0, self.spread, 20000),
                    "dy_mm": rng.normal(0.0, self.spread, 20000),
                }
            )
        )


def example_plot_xy_hexbin(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Plot Type: Xy Hexbin."""
    bench = DenseCloud().to_bench(run_cfg)
    res = bench.plot_sweep(input_vars=["spread"], result_vars=["touches"])
    bench.report.append(
        res.to(XYHexbinResult, x="dx_mm", y="dy_mm", gridsize=30, min_count=1, data_aspect=1)
    )

    return bench


if __name__ == "__main__":
    bn.run(example_plot_xy_hexbin, subsampling_divisions=3)
