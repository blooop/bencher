import bencher as bn

import xarray as xr
import numpy as np
import holoviews as hv


class ExampleMergeDataset(bn.ParametrizedSweep):
    value = bn.FloatSweep(default=0, bounds=[0, 10])
    repeats_x = bn.IntSweep(default=2, bounds=[2, 4])
    # repeats_y = bn.IntSweep(default=2, bounds=[2, 4])

    result_df = bn.ResultDataSet()

    def __call__(self, **kwargs):
        self.update_params_from_kwargs(**kwargs)
        # First, create a DataArray from the vector
        vector = [v + self.value for v in range(1, self.repeats_x)]
        data_array = xr.DataArray(vector, dims=["index"], coords={"index": np.arange(len(vector))})
        # Convert the DataArray to a Dataset
        result_df = xr.Dataset({"result_df": data_array})
        self.result_df = bn.ResultDataSet(result_df.to_pandas())
        return super().__call__(**kwargs)


def example_dataset(run_cfg: bn.BenchRunCfg | None = None):
    bench = ExampleMergeDataset().to_bench(run_cfg)
    bench.plot_sweep(input_vars=["value"], const_vars=dict(repeats_x=4))
    # bench.report.append(res.to_panes(target_dimension=1))
    # bench.report.append(res.to_panes(target_dimension=2))
    # bench.reprt.append(res.to_video_grid
    #                             # bn.BenchResult.to_video_grid,
    #     target_duration=0.06,
    #     compose_method_list=[
    #         bn.ComposeType.right,
    #         bn.ComposeType.right,
    #         bn.ComposeType.sequence,
    #     ],
    # )
    # bench.report.append(res.to_panes(container=hv.Bars,target_dimension=1))
    # bench.report.append(res.to_panes(container=hv.Curve))
    bench.add(bn.DataSetResult, container=hv.Curve)
    return bench


if __name__ == "__main__":
    bn.run(example_dataset)
