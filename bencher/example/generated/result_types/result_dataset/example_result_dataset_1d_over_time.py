"""Auto-generated example: Result Dataset: 1D input, over time."""

import math
from datetime import datetime, timedelta

import bencher as bn


class TimeseriesCollector(bn.ParametrizedSweep):
    """Collects a timeseries whose amplitude drifts between runs.

    Each plot_sweep call below is one time snapshot; over_time=True stacks the
    snapshots into a history. A ResultDataSet cell stores a path into the blob
    store, so every history point stays renderable and the report shows a
    labelled per-time grid with one curve per snapshot instead of only the
    latest run.
    """

    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")

    result_ds = bn.ResultDataSet(
        container=bn.xy_curve(x="time", y="result_ds", markers=True),
        doc="Collected timeseries dataset",
    )

    _drift = 0.0  # set externally per snapshot

    def benchmark(self):
        import xarray as xr

        n_samples = max(1, int(self.duration))
        gain = 1.0 + 0.5 * self._drift
        values = [
            math.sin(2 * math.pi * i / max(n_samples, 1)) * self.duration * gain
            for i in range(n_samples)
        ]
        data_array = xr.DataArray(values, dims=["time"], coords={"time": list(range(n_samples))})
        ds = xr.Dataset({"result_ds": data_array})
        self.result_ds = bn.ResultDataSet(ds.to_pandas())


def example_result_dataset_1d_over_time(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Result Dataset: 1D input, over time."""
    if run_cfg is None:
        run_cfg = bn.BenchRunCfg()

    benchable = TimeseriesCollector()
    bench = benchable.to_bench(run_cfg)

    base_time = datetime(2024, 1, 1)
    n_snapshots = 3
    for i in range(n_snapshots):
        benchable._drift = float(i)
        run_cfg.cache.clear = True
        run_cfg.time.clear_history = i == 0
        run_cfg.visualization.auto_plot = i == n_snapshots - 1
        bench.plot_sweep(
            "dataset_over_time",
            input_vars=["duration"],
            result_vars=["result_ds"],
            run_cfg=run_cfg,
            time_src=base_time + timedelta(seconds=i),
            description="Demonstrates an xarray/pandas dataset tracked with over_time=True. Dataset cells are stored as blob-store paths, so the report renders every history point as a labelled per-time grid of curves rather than only the latest run.",
            post_description="Each column of the grid is one time snapshot, labelled with its timestamp. The curve amplitude grows between snapshots, showing that each history point renders its own stored dataset.",
        )

    return bench


if __name__ == "__main__":
    bn.run(example_result_dataset_1d_over_time, subsampling_divisions=3, over_time=True)
