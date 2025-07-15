import logging
from typing import List, Any, Tuple, Optional
from enum import Enum, auto
import xarray as xr
from param import Parameter
import holoviews as hv
from functools import partial
import panel as pn
import numpy as np
from textwrap import wrap

from bencher.utils import int_to_col, color_tuple_to_css, callable_name

from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.inputs import with_level

from bencher.variables.results import OptDir
from copy import deepcopy
from bencher.variables.results import ResultVar
from bencher.plotting.plot_filter import VarRange, PlotFilter
from bencher.utils import listify

from bencher.variables.results import ResultReference, ResultDataSet

from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)

from collections import defaultdict

import pandas as pd

from bencher.bench_cfg import BenchCfg
from bencher.plotting.plt_cnt_cfg import PltCntCfg

# todo add plugins
# https://gist.github.com/dorneanu/cce1cd6711969d581873a88e0257e312
# https://kaleidoescape.github.io/decorated-plugins/


class ReduceType(Enum):
    AUTO = auto()  # automatically determine the best way to reduce the dataset
    SQUEEZE = auto()  # remove any dimensions of length 1
    REDUCE = auto()  # get the mean and std dev of the data along the "repeat" dimension
    MINMAX = auto()  # get the minimum and maximum of data along the "repeat" dimension
    NONE = auto()  # don't reduce


class EmptyContainer:
    """A wrapper for list like containers that only appends if the item is not None"""

    def __init__(self, pane) -> None:
        self.pane = pane

    def append(self, child):
        if child is not None:
            self.pane.append(child)

    def get(self):
        return self.pane if len(self.pane) > 0 else None


def convert_dataset_bool_dims_to_str(dataset: xr.Dataset) -> xr.Dataset:
    """Given a dataarray that contains boolean coordinates, convert them to strings so that holoviews loads the data properly

    Args:
        dataarray (xr.DataArray): dataarray with boolean coordinates

    Returns:
        xr.DataArray: dataarray with boolean coordinates converted to strings
    """
    bool_coords = {}
    for c in dataset.coords:
        if dataset.coords[c].dtype == bool:
            bool_coords[c] = [str(vals) for vals in dataset.coords[c].values]

    if len(bool_coords) > 0:
        return dataset.assign_coords(bool_coords)
    return dataset


class BenchResultBase:
    def __init__(self, bench_cfg: BenchCfg) -> None:
        self.bench_cfg = bench_cfg
        # self.wrap_long_time_labels(bench_cfg)  # todo remove
        self.ds = xr.Dataset()
        self.object_index = []
        self.hmaps = defaultdict(dict)
        self.result_hmaps = bench_cfg.result_hmaps
        self.studies = []
        self.plt_cnt_cfg = PltCntCfg()
        self.plot_inputs = []
        self.dataset_list = []

        # self.width=600/
        # self.height=600

        #   bench_res.objects.append(rv)
        # bench_res.reference_index = len(bench_res.objects)

    def to_xarray(self) -> xr.Dataset:
        return self.ds

    def setup_object_index(self):
        self.object_index = []

    def to_pandas(self, reset_index=True) -> pd.DataFrame:
        """Get the xarray results as a pandas dataframe

        Returns:
            pd.DataFrame: The xarray results array as a pandas dataframe
        """
        ds = self.to_xarray().to_dataframe()
        return ds.reset_index() if reset_index else ds

    def wrap_long_time_labels(self, bench_cfg):
        """Takes a benchCfg and wraps any index labels that are too long to be plotted easily

        Args:
            bench_cfg (BenchCfg):

        Returns:
            BenchCfg: updated config with wrapped labels
        """
        if bench_cfg.over_time:
            if self.ds.coords["over_time"].dtype == np.datetime64:
                # plotly catastrophically fails to plot anything with the default long string representation of time, so convert to a shorter time representation
                self.ds.coords["over_time"] = [
                    pd.to_datetime(t).strftime("%d-%m-%y %H-%M-%S")
                    for t in self.ds.coords["over_time"].values
                ]
                # wrap very long time event labels because otherwise the graphs are unreadable
            if bench_cfg.time_event is not None:
                self.ds.coords["over_time"] = [
                    "\n".join(wrap(t, 20)) for t in self.ds.coords["over_time"].values
                ]
        return bench_cfg

    def post_setup(self):
        self.plt_cnt_cfg = PltCntCfg.generate_plt_cnt_cfg(self.bench_cfg)
        self.bench_cfg = self.wrap_long_time_labels(self.bench_cfg)
        self.ds = convert_dataset_bool_dims_to_str(self.ds)

    def result_samples(self) -> int:
        """The number of samples in the results dataframe"""
        return self.ds.count()

    def to_hv_dataset(
        self,
        reduce: ReduceType = ReduceType.AUTO,
        result_var: ResultVar = None,
        level: int = None,
    ) -> hv.Dataset:
        """Generate a holoviews dataset from the xarray dataset.

        Args:
            reduce (ReduceType, optional): Optionally perform reduce options on the dataset.  By default the returned dataset will calculate the mean and standard deviation over the "repeat" dimension so that the dataset plays nicely with most of the holoviews plot types.  Reduce.Sqeeze is used if there is only 1 repeat and you want the "reduce" variable removed from the dataset. ReduceType.None returns an unaltered dataset. Defaults to ReduceType.AUTO.

        Returns:
            hv.Dataset: results in the form of a holoviews dataset
        """

        if reduce == ReduceType.NONE:
            kdims = [i.name for i in self.bench_cfg.all_vars]
            return hv.Dataset(self.to_dataset(reduce, result_var, level), kdims=kdims)
        return hv.Dataset(self.to_dataset(reduce, result_var, level))

    def to_dataset(
        self,
        reduce: ReduceType = ReduceType.AUTO,
        result_var: ResultVar | str = None,
        level: int = None,
    ) -> xr.Dataset:
        """Generate a summarised xarray dataset.

        Args:
            reduce (ReduceType, optional): Optionally perform reduce options on the dataset.  By default the returned dataset will calculate the mean and standard deviation over the "repeat" dimension so that the dataset plays nicely with most of the holoviews plot types.  Reduce.Sqeeze is used if there is only 1 repeat and you want the "reduce" variable removed from the dataset. ReduceType.None returns an unaltered dataset. Defaults to ReduceType.AUTO.

        Returns:
            xr.Dataset: results in the form of an xarray dataset
        """
        if reduce == ReduceType.AUTO:
            reduce = ReduceType.REDUCE if self.bench_cfg.repeats > 1 else ReduceType.SQUEEZE

        ds_out = self.ds.copy()

        if result_var is not None:
            if isinstance(result_var, Parameter):
                var_name = result_var.name
            elif isinstance(result_var, str):
                var_name = result_var
            else:
                raise TypeError(
                    f"Unsupported type for result_var: {type(result_var)}. Expected Parameter or str."
                )
            ds_out = ds_out[var_name].to_dataset(name=var_name)

        def rename_ds(dataset: xr.Dataset, suffix: str):
            # var_name =
            rename_dict = {var: f"{var}_{suffix}" for var in dataset.data_vars}
            ds = dataset.rename_vars(rename_dict)
            return ds

        match reduce:
            case ReduceType.REDUCE:
                ds_reduce_mean = ds_out.mean(dim="repeat", keep_attrs=True)
                ds_reduce_std = ds_out.std(dim="repeat", keep_attrs=False)
                ds_reduce_std = rename_ds(ds_reduce_std, "std")
                ds_out = xr.merge([ds_reduce_mean, ds_reduce_std])
                ds_out = xr.merge(
                    [
                        ds_reduce_mean,
                        ds_reduce_std,
                    ]
                )
            case ReduceType.MINMAX:  # TODO, need to pass mean, center of minmax, and minmax
                ds_reduce_mean = ds_out.mean(dim="repeat", keep_attrs=True)
                ds_reduce_min = ds_out.min(dim="repeat")
                ds_reduce_max = ds_out.max(dim="repeat")
                ds_reduce_range = rename_ds(ds_reduce_max - ds_reduce_min, "range")
                ds_out = xr.merge([ds_reduce_mean, ds_reduce_range])
            case ReduceType.SQUEEZE:
                ds_out = ds_out.squeeze(drop=True)
        if level is not None:
            coords_no_repeat = {}
            for c, v in ds_out.coords.items():
                if c != "repeat":
                    coords_no_repeat[c] = with_level(v.to_numpy(), level)
            return ds_out.sel(coords_no_repeat)
        return ds_out

    def get_optimal_vec(
        self,
        result_var: ParametrizedSweep,
        input_vars: List[ParametrizedSweep],
    ) -> List[Any]:
        """Get the optimal values from the sweep as a vector.

        Args:
            result_var (bch.ParametrizedSweep): Optimal values of this result variable
            input_vars (List[bch.ParametrizedSweep]): Define which input vars values are returned in the vector

        Returns:
            List[Any]: A vector of optimal values for the desired input vector
        """

        da = self.get_optimal_value_indices(result_var)
        output = []
        for iv in input_vars:
            if da.coords[iv.name].values.size == 1:
                # https://stackoverflow.com/questions/773030/why-are-0d-arrays-in-numpy-not-considered-scalar
                # use [()] to convert from a 0d numpy array to a scalar
                output.append(da.coords[iv.name].values[()])
            else:
                logging.warning(f"values size: {da.coords[iv.name].values.size}")
                output.append(max(da.coords[iv.name].values[()]))
            logging.info(f"Maximum value of {iv.name}: {output[-1]}")
        return output

    def get_optimal_value_indices(self, result_var: ParametrizedSweep) -> xr.DataArray:
        """Get an xarray mask of the values with the best values found during a parameter sweep

        Args:
            result_var (bch.ParametrizedSweep): Optimal value of this result variable

        Returns:
            xr.DataArray: xarray mask of optimal values
        """
        result_da = self.ds[result_var.name]
        if result_var.direction == OptDir.maximize:
            opt_val = result_da.max()
        else:
            opt_val = result_da.min()
        indices = result_da.where(result_da == opt_val, drop=True).squeeze()
        logging.info(f"optimal value of {result_var.name}: {opt_val.values}")
        return indices

    def get_optimal_inputs(
        self,
        result_var: ParametrizedSweep,
        keep_existing_consts: bool = True,
        as_dict: bool = False,
    ) -> Tuple[ParametrizedSweep, Any] | dict[ParametrizedSweep, Any]:
        """Get a list of tuples of optimal variable names and value pairs, that can be fed in as constant values to subsequent parameter sweeps

        Args:
            result_var (bch.ParametrizedSweep): Optimal values of this result variable
            keep_existing_consts (bool): Include any const values that were defined as part of the parameter sweep
            as_dict (bool): return value as a dictionary

        Returns:
            Tuple[bch.ParametrizedSweep, Any]|[ParametrizedSweep, Any]: Tuples of variable name and optimal values
        """
        da = self.get_optimal_value_indices(result_var)
        if keep_existing_consts:
            output = deepcopy(self.bench_cfg.const_vars)
        else:
            output = []

        for iv in self.bench_cfg.input_vars:
            # assert da.coords[iv.name].values.size == (1,)
            if da.coords[iv.name].values.size == 1:
                # https://stackoverflow.com/questions/773030/why-are-0d-arrays-in-numpy-not-considered-scalar
                # use [()] to convert from a 0d numpy array to a scalar
                output.append((iv, da.coords[iv.name].values[()]))
            else:
                logging.warning(f"values size: {da.coords[iv.name].values.size}")
                output.append((iv, max(da.coords[iv.name].values[()])))

            logging.info(f"Maximum value of {iv.name}: {output[-1][1]}")
        if as_dict:
            return dict(output)
        return output

    def describe_sweep(self):
        return self.bench_cfg.describe_sweep()

    def get_hmap(self, name: str = None):
        try:
            if name is None:
                name = self.result_hmaps[0].name
            if name in self.hmaps:
                return self.hmaps[name]
        except Exception as e:
            raise RuntimeError(
                "You are trying to plot a holomap result but it is not in the result_vars list.  Add the holomap to the result_vars list"
            ) from e
        return None

    def to_plot_title(self) -> str:
        if len(self.bench_cfg.input_vars) > 0 and len(self.bench_cfg.result_vars) > 0:
            return f"{self.bench_cfg.result_vars[0].name} vs {self.bench_cfg.input_vars[0].name}"
        return ""

    def title_from_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        if "title" in kwargs:
            return kwargs["title"]

        if isinstance(dataset, xr.DataArray):
            tit = [dataset.name]
            for d in dataset.dims:
                tit.append(d)
        else:
            tit = [result_var.name]
            tit.extend(list(dataset.sizes))

        return " vs ".join(tit)

    def get_results_var_list(self, result_var: ParametrizedSweep = None) -> List[ResultVar]:
        return self.bench_cfg.result_vars if result_var is None else listify(result_var)

    def map_plots(
        self,
        plot_callback: callable,
        result_var: ParametrizedSweep = None,
        row: EmptyContainer = None,
    ) -> Optional[pn.Row]:
        if row is None:
            row = EmptyContainer(pn.Row(name=self.to_plot_title()))
        for rv in self.get_results_var_list(result_var):
            row.append(plot_callback(rv))
        return row.get()

    @staticmethod
    def zip_results1D(args):  # pragma: no cover
        first_el = [a[0] for a in args]
        out = pn.Column()
        for a in zip(*first_el):
            row = pn.Row()
            row.append(a[0])
            for a1 in range(1, len(a[1])):
                row.append(a[a1][1])
            out.append(row)
        return out

    @staticmethod
    def zip_results1D1(panel_list):  # pragma: no cover
        container_args = {"styles": {}}
        container_args["styles"]["border-bottom"] = f"{2}px solid grey"
        print(panel_list)
        out = pn.Column()
        for a in zip(*panel_list):
            row = pn.Row(**container_args)
            row.append(a[0][0])
            for a1 in range(0, len(a)):
                row.append(a[a1][1])
            out.append(row)
        return out

    @staticmethod
    def zip_results1D2(panel_list):  # pragma: no cover
        if panel_list is not None:
            print(panel_list)
            primary = panel_list[0]
            secondary = panel_list[1:]
            for i in range(len(primary)):
                print(type(primary[i]))
                if isinstance(primary[i], (pn.Column, pn.Row)):
                    for j in range(len(secondary)):
                        primary[i].append(secondary[j][i][1])
            return primary
        return panel_list

    def map_plot_panes(
        self,
        plot_callback: callable,
        hv_dataset: hv.Dataset = None,
        target_dimension: int = 2,
        result_var: ResultVar = None,
        result_types=None,
        pane_collection: pn.pane = None,
        zip_results=False,
        reduce: ReduceType = None,
        **kwargs,
    ) -> Optional[pn.Row]:
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(reduce=reduce)

        if pane_collection is None:
            pane_collection = pn.Row()

        row = EmptyContainer(pane_collection)

        # kwargs= self.set_plot_size(**kwargs)
        for rv in self.get_results_var_list(result_var):
            if result_types is None or isinstance(rv, result_types):
                row.append(
                    self.to_panes_multi_panel(
                        hv_dataset,
                        rv,
                        plot_callback=partial(plot_callback, **kwargs),
                        target_dimension=target_dimension,
                    )
                )

        if zip_results:
            return self.zip_results1D2(row.get())
        return row.get()

    def filter(
        self,
        plot_callback: callable,
        plot_filter=None,
        float_range: VarRange = VarRange(0, None),
        cat_range: VarRange = VarRange(0, None),
        vector_len: VarRange = VarRange(1, 1),
        result_vars: VarRange = VarRange(1, 1),
        panel_range: VarRange = VarRange(0, 0),
        repeats_range: VarRange = VarRange(1, None),
        input_range: VarRange = VarRange(1, None),
        reduce: ReduceType = ReduceType.AUTO,
        target_dimension: int = 2,
        result_var: ResultVar = None,
        result_types=None,
        pane_collection: pn.pane = None,
        override=False,
        **kwargs,
    ) -> Optional[pn.panel]:
        plot_filter = PlotFilter(
            float_range=float_range,
            cat_range=cat_range,
            vector_len=vector_len,
            result_vars=result_vars,
            panel_range=panel_range,
            repeats_range=repeats_range,
            input_range=input_range,
        )
        matches_res = plot_filter.matches_result(
            self.plt_cnt_cfg, callable_name(plot_callback), override
        )
        if matches_res.overall:
            return self.map_plot_panes(
                plot_callback=plot_callback,
                hv_dataset=None,
                target_dimension=target_dimension,
                result_var=result_var,
                result_types=result_types,
                pane_collection=pane_collection,
                reduce=reduce,
                **kwargs,
            )
        return matches_res.to_panel()

    def to_panes_multi_panel(
        self,
        hv_dataset: hv.Dataset,
        result_var: ResultVar,
        plot_callback: callable = None,
        target_dimension: int = 1,
        **kwargs,
    ):
        dims = len(hv_dataset.dimensions())
        if target_dimension is None:
            target_dimension = dims
        return self._to_panes_da(
            hv_dataset.data,
            plot_callback=plot_callback,
            target_dimension=target_dimension,
            horizontal=dims <= target_dimension + 1,
            result_var=result_var,
            **kwargs,
        )

    def _to_panes_da(
        self,
        dataset: xr.Dataset,
        plot_callback: callable = None,
        target_dimension=1,
        horizontal=False,
        result_var=None,
        **kwargs,
    ) -> pn.panel:
        # todo, when dealing with time and repeats, add feature to allow custom order of dimension recursion
        ##todo remove recursion
        num_dims = len(dataset.sizes)
        # print(f"num_dims: {num_dims}, horizontal: {horizontal}, target: {target_dimension}")
        dims = list(d for d in dataset.sizes)

        time_dim_delta = 0
        if self.bench_cfg.over_time:
            time_dim_delta = 0

        if num_dims > (target_dimension + time_dim_delta) and num_dims != 0:
            selected_dim = dims[-1]
            # print(f"selected dim {dim_sel}")
            dim_color = color_tuple_to_css(int_to_col(num_dims - 2, 0.05, 1.0))

            outer_container = ComposableContainerPanel(
                name=" vs ".join(dims),
                background_col=dim_color,
                horizontal=not horizontal,
            )
            max_len = 0
            for i in range(dataset.sizes[selected_dim]):
                sliced = dataset.isel({selected_dim: i})
                label_val = sliced.coords[selected_dim].values.item()
                inner_container = ComposableContainerPanel(
                    name=outer_container.name,
                    width=num_dims - target_dimension,
                    var_name=selected_dim,
                    var_value=label_val,
                    horizontal=horizontal,
                )

                panes = self._to_panes_da(
                    sliced,
                    plot_callback=plot_callback,
                    target_dimension=target_dimension,
                    horizontal=len(sliced.sizes) <= target_dimension + 1,
                    result_var=result_var,
                )
                max_len = max(max_len, inner_container.label_len)
                inner_container.append(panes)
                outer_container.append(inner_container.container)
            for c in outer_container.container:
                c[0].width = max_len * 7
        else:
            return plot_callback(dataset=dataset, result_var=result_var, **kwargs)

        return outer_container.container

    def zero_dim_da_to_val(self, da_ds: xr.DataArray | xr.Dataset) -> Any:
        # todo this is really horrible, need to improve
        dim = None
        if isinstance(da_ds, xr.Dataset):
            dim = list(da_ds.keys())[0]
            da = da_ds[dim]
        else:
            da = da_ds

        for k in da.coords.keys():
            dim = k
            break
        if dim is None:
            return da_ds.values.squeeze().item()
        return da.expand_dims(dim).values[0]

    def ds_to_container(  # pylint: disable=too-many-return-statements
        self, dataset: xr.Dataset, result_var: Parameter, container, **kwargs
    ) -> Any:
        val = self.zero_dim_da_to_val(dataset[result_var.name])
        if isinstance(result_var, ResultDataSet):
            ref = self.dataset_list[val]
            if ref is not None:
                if container is not None:
                    return container(ref.obj)
                return ref.obj
            return None
        if isinstance(result_var, ResultReference):
            ref = self.object_index[val]
            if ref is not None:
                val = ref.obj
                if ref.container is not None:
                    return ref.container(val, **kwargs)
        if container is not None:
            return container(val, styles={"background": "white"}, **kwargs)
        try:
            container = result_var.to_container()
            if container is not None:
                return container(val)
        except AttributeError as _:
            # TODO make sure all vars have to_container method
            pass
        return val

    @staticmethod
    def select_level(
        dataset: xr.Dataset,
        level: int,
        include_types: List[type] = None,
        exclude_names: List[str] = None,
    ) -> xr.Dataset:
        """Given a dataset, return a reduced dataset that only contains data from a specified level.  By default all types of variables are filtered at the specified level.  If you only want to get a reduced level for some types of data you can pass in a list of types to get filtered, You can also pass a list of variables names to exclude from getting filtered
        Args:
            dataset (xr.Dataset): dataset to filter
            level (int): desired data resolution level
            include_types (List[type], optional): Only filter data of these types. Defaults to None.
            exclude_names (List[str], optional): Only filter data with these variable names. Defaults to None.

        Returns:
            xr.Dataset: A reduced dataset at the specified level

        Example:  a dataset with float_var: [1,2,3,4,5] cat_var: [a,b,c,d,e]

        select_level(ds,2) -> [1,5] [a,e]
        select_level(ds,2,(float)) -> [1,5] [a,b,c,d,e]
        select_level(ds,2,exclude_names=["cat_var]) -> [1,5] [a,b,c,d,e]

        see test_bench_result_base.py -> test_select_level()
        """
        coords_no_repeat = {}
        for c, v in dataset.coords.items():
            if c != "repeat":
                vals = v.to_numpy()
                print(vals.dtype)
                include = True
                if include_types is not None and vals.dtype not in listify(include_types):
                    include = False
                if exclude_names is not None and c in listify(exclude_names):
                    include = False
                if include:
                    coords_no_repeat[c] = with_level(v.to_numpy(), level)
        return dataset.sel(coords_no_repeat)

    # MAPPING TO LOWER LEVEL BENCHCFG functions so they are available at a top level.
    def to_sweep_summary(self, **kwargs):
        return self.bench_cfg.to_sweep_summary(**kwargs)

    def to_title(self, panel_name: str = None) -> pn.pane.Markdown:
        return self.bench_cfg.to_title(panel_name)

    def to_description(self, width: int = 800) -> pn.pane.Markdown:
        return self.bench_cfg.to_description(width)

    def set_plot_size(self, **kwargs) -> dict:
        if "width" not in kwargs:
            if self.bench_cfg.plot_size is not None:
                kwargs["width"] = self.bench_cfg.plot_size
            # specific width overrides general size
            if self.bench_cfg.plot_width is not None:
                kwargs["width"] = self.bench_cfg.plot_width

        if "height" not in kwargs:
            if self.bench_cfg.plot_size is not None:
                kwargs["height"] = self.bench_cfg.plot_size
            # specific height overrides general size
            if self.bench_cfg.plot_height is not None:
                kwargs["height"] = self.bench_cfg.plot_height
        return kwargs
