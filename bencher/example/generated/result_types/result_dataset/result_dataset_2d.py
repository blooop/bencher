"""Auto-generated example: Result Dataset: 2D input."""

from typing import Any

import math
import bencher as bch


class TimeseriesCollector(bch.ParametrizedSweep):
    """Collects a timeseries and returns it as an xarray dataset."""

    duration = bch.FloatSweep(default=5.0, bounds=[1.0, 10.0], doc="Collection duration")
    sample_rate = bch.FloatSweep(default=1.0, bounds=[0.5, 2.0], doc="Samples per second")

    result_ds = bch.ResultDataSet(doc="Collected timeseries dataset")

    def __call__(self, **kwargs: Any) -> Any:
        import xarray as xr

        self.update_params_from_kwargs(**kwargs)
        n_samples = max(1, int(self.duration * self.sample_rate))
        values = [
            math.sin(2 * math.pi * i / max(n_samples, 1)) * self.duration for i in range(n_samples)
        ]
        data_array = xr.DataArray(values, dims=["time"], coords={"time": list(range(n_samples))})
        ds = xr.Dataset({"result_ds": data_array})
        self.result_ds = bch.ResultDataSet(ds.to_pandas())
        return super().__call__()


def example_result_dataset_2d(run_cfg: bch.BenchRunCfg | None = None) -> bch.Bench:
    """Result Dataset: 2D input."""
    bench = TimeseriesCollector().to_bench(run_cfg)
    bench.plot_sweep(
        input_vars=["duration", "sample_rate"],
        result_vars=["result_ds"],
        description="Demonstrates an xarray/pandas dataset with 2D input sweep.",
    )

    return bench


if __name__ == "__main__":
    bch.run(example_result_dataset_2d, level=2)
