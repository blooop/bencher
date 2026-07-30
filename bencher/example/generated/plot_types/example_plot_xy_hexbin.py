"""Auto-generated example: Plot Type: Xy Hexbin."""

import numpy as np
import pandas as pd

import bencher as bn


class DenseCloud(bn.ParametrizedSweep):
    """Too many points to read as markers, so the marks become counts."""

    spread = bn.FloatSweep(default=0.5, bounds=[0.2, 1.0], doc="Positioning noise")

    touches = bn.ResultDataSet(
        container=bn.xy_hexbin(
            x="dx_mm",
            y="dy_mm",
            gridsize=30,
            min_count=1,
            data_aspect=1,
        ),
        doc="Landing points, one row per touch",
    )

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
    bench.plot_sweep(input_vars=["spread"], result_vars=["touches"])

    return bench


if __name__ == "__main__":
    bn.run(example_plot_xy_hexbin, subsampling_divisions=3)
