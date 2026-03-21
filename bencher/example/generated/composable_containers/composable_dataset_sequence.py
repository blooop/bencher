"""Auto-generated example: Composable Dataset: ComposeType.sequence."""

from typing import Any

import bencher as bn


class TimeseriesCollector(bn.ParametrizedSweep):
    """Collects time-series data into an xarray dataset."""

    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")
    result_ds = bn.ResultDataSet(doc="Collected time-series dataset")

    def __call__(self, **kwargs: Any) -> Any:
        import xarray as xr
        import numpy as np

        self.update_params_from_kwargs(**kwargs)
        n = int(self.duration * 10)
        t = np.linspace(0, self.duration, n)
        values = np.sin(2 * np.pi * t / self.duration) * self.duration
        data_array = xr.DataArray(values, dims=["time"], coords={"time": t})
        self.result_ds = bn.ResultDataSet(xr.Dataset({"signal": data_array}).to_pandas())
        return super().__call__()


def example_composable_dataset_sequence(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Composable Dataset: ComposeType.sequence."""
    bench = TimeseriesCollector().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["duration"], result_vars=["result_ds"])

    return bench


if __name__ == "__main__":
    bn.run(example_composable_dataset_sequence, level=3)
