"""Auto-generated example: Composable Dataset: ComposeType.overlay."""

import bencher as bn


class TimeseriesCollector(bn.ParametrizedSweep):
    """Collects time-series data into an xarray dataset."""

    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")
    result_ds = bn.ResultDataSet(doc="Collected time-series dataset")

    def benchmark(self):
        import xarray as xr
        import numpy as np

        n = int(self.duration * 10)
        t = np.linspace(0, self.duration, n)
        values = np.sin(2 * np.pi * t / self.duration) * self.duration
        data_array = xr.DataArray(values, dims=["time"], coords={"time": t})
        self.result_ds = bn.ResultDataSet(xr.Dataset({"signal": data_array}).to_pandas())


def example_composable_dataset_overlay(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Composable Dataset: ComposeType.overlay."""
    bench = TimeseriesCollector().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["duration"], result_vars=["result_ds"])

    return bench


if __name__ == "__main__":
    bn.run(example_composable_dataset_overlay, level=3)
