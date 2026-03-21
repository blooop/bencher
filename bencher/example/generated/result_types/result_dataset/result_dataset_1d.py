"""Auto-generated example: Result Dataset: 1D input."""

from typing import Any

import math

import bencher as bn


class TimeseriesCollector(bn.ParametrizedSweep):
    """Collects a timeseries and returns it as an xarray dataset."""

    duration = bn.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")
    sample_rate = bn.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Samples per second")

    result_ds = bn.ResultDataSet(doc="Collected timeseries dataset")

    def __call__(self, **kwargs: Any) -> Any:
        import xarray as xr

        self.update_params_from_kwargs(**kwargs)
        n_samples = max(1, int(self.duration * self.sample_rate))
        values = [
            math.sin(2 * math.pi * i / max(n_samples, 1)) * self.duration for i in range(n_samples)
        ]
        data_array = xr.DataArray(values, dims=["time"], coords={"time": list(range(n_samples))})
        ds = xr.Dataset({"result_ds": data_array})
        self.result_ds = bn.ResultDataSet(ds.to_pandas())
        return super().__call__()


def example_result_dataset_1d(run_cfg: bn.BenchRunCfg | None = None) -> bn.Bench:
    """Result Dataset: 1D input."""
    bench = TimeseriesCollector().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["duration"],
        result_vars=["result_ds"],
        description="Demonstrates an xarray/pandas dataset with 1D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bn.run(example_result_dataset_1d, level=3)
