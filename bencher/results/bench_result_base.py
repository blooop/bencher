from __future__ import annotations

import logging
import os
from typing import Any, Literal, Callable
from enum import Enum, auto
import numpy as np
import xarray as xr
from param import Parameter
import holoviews as hv
from functools import partial
import panel as pn
from textwrap import wrap

from bencher.utils import int_to_col, color_tuple_to_css, callable_name

from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.inputs import with_level

from bencher.variables.results import OptDir
from copy import deepcopy
from bencher.variables.results import ResultFloat, ResultBool
from bencher.plotting.plot_filter import VarRange, PlotFilter
from bencher.utils import listify

from bencher.variables.results import (
    ResultReference,
    ResultDataSet,
    ResultVideo,
    ResultImage,
    ResultRerun,
)

from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
    make_label_pane,
)
from bencher.results.composable_container.composable_container_base import (
    ComposeType,
    ComposableContainerBase,
    PaneLayout,
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
        self.regression_report = None
        self.perf_report = None
        self._to_dataset_cache: dict = {}

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
        """Takes a benchCfg and formats over_time coordinate labels for display.

        For discrete TimeEvent labels, wraps long strings for readability.
        For datetime TimeSnapshot labels, replaces with integer indices so that
        Panel renders a slider widget.  Without this, Panel's DiscreteSlider
        truncates np.datetime64 values to second precision, which causes
        sub-second timestamps to collide into fewer slider positions.

        Args:
            bench_cfg (BenchCfg):

        Returns:
            BenchCfg: updated config with wrapped labels
        """
        if bench_cfg.over_time and "over_time" in self.ds.coords:
            if bench_cfg.time_event is not None:
                self.ds.coords["over_time"] = [
                    "\n".join(wrap(str(t), 30)) for t in self.ds.coords["over_time"].values
                ]
            else:
                time_values = self.ds.coords["over_time"].values
                if len(time_values) > 1:
                    # Panel's DiscreteSlider formats datetime64 at second precision.
                    # When timestamps are sub-second apart, labels collide and the
                    # slider shows fewer positions than time points.  Fix by spacing
                    # timestamps at least 1 second apart when collisions are detected.
                    sec_labels = [
                        pd.Timestamp(t).strftime("%Y-%m-%d %H:%M:%S") for t in time_values
                    ]
                    if len(set(sec_labels)) < len(sec_labels):
                        base = time_values[0]
                        self.ds.coords["over_time"] = [
                            base + np.timedelta64(i, "s") for i in range(len(time_values))
                        ]
        return bench_cfg

    def post_setup(self):
        self.plt_cnt_cfg = PltCntCfg.generate_plt_cnt_cfg(self.bench_cfg)
        self.bench_cfg = self.wrap_long_time_labels(self.bench_cfg)
        self.ds = convert_dataset_bool_dims_to_str(self.ds)
        self._to_dataset_cache.clear()

    def result_samples(self) -> int:
        """The number of samples in the results dataframe"""
        return self.ds.count()

    def to_hv_dataset(
        self,
        reduce: ReduceType = ReduceType.AUTO,
        result_var: ResultFloat | None = None,
        level: int | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: Literal["mean", "sum", "max", "min", "median"] | None = None,
    ) -> hv.Dataset:
        """Generate a holoviews dataset from the xarray dataset.

        Args:
            reduce (ReduceType, optional): Optionally perform reduce options on the dataset.  By default the returned dataset will calculate the mean and standard deviation over the "repeat" dimension so that the dataset plays nicely with most of the holoviews plot types.  Reduce.Sqeeze is used if there is only 1 repeat and you want the "reduce" variable removed from the dataset. ReduceType.None returns an unaltered dataset. Defaults to ReduceType.AUTO.

        Returns:
            hv.Dataset: results in the form of a holoviews dataset
        """

        if reduce == ReduceType.NONE:
            ds_out = self.to_dataset(
                reduce,
                result_var=result_var,
                level=level,
                agg_over_dims=agg_over_dims,
                agg_fn=agg_fn,
                deep=False,
            )
            # Filter kdims to only those that survived aggregation
            kdims = [i.name for i in self.bench_cfg.all_vars if i.name in ds_out.dims]
            return hv.Dataset(ds_out, kdims=kdims)
        return hv.Dataset(
            self.to_dataset(
                reduce,
                result_var=result_var,
                level=level,
                agg_over_dims=agg_over_dims,
                agg_fn=agg_fn,
                deep=False,
            )
        )

    def _resolve_auto(self, reduce: ReduceType) -> ReduceType:
        """Resolve AUTO to a concrete ReduceType based on repeat count."""
        if reduce == ReduceType.AUTO:
            return ReduceType.REDUCE if self.bench_cfg.repeats > 1 else ReduceType.SQUEEZE
        return reduce

    def _to_dataset_cache_key(
        self,
        reduce: ReduceType,
        result_var: ResultFloat | str | None,
        level: int | None,
        agg_over_dims: list[str] | None,
        agg_fn: str | None,
    ) -> tuple:
        """Build a hashable cache key from normalized to_dataset() arguments."""
        reduce = self._resolve_auto(reduce)
        rv_key = result_var.name if isinstance(result_var, Parameter) else result_var
        # Normalize dimension order so aggregation over the same set shares cache entries
        dims_key = tuple(sorted(agg_over_dims)) if agg_over_dims else None
        # fn is irrelevant when no agg dims — aggregation is skipped entirely
        fn_key = (agg_fn or "mean").lower() if agg_over_dims else None
        return (reduce, rv_key, level, dims_key, fn_key)

    def to_dataset(
        self,
        reduce: ReduceType = ReduceType.AUTO,
        result_var: ResultFloat | str | None = None,
        level: int | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: Literal["mean", "sum", "max", "min", "median"] | None = None,
        deep: bool = True,
    ) -> xr.Dataset:
        """Generate a summarised xarray dataset.

        Args:
            reduce (ReduceType, optional): Optionally perform reduce options on the dataset.  By default the returned dataset will calculate the mean and standard deviation over the "repeat" dimension so that the dataset plays nicely with most of the holoviews plot types.  Reduce.Sqeeze is used if there is only 1 repeat and you want the "reduce" variable removed from the dataset. ReduceType.None returns an unaltered dataset. Defaults to ReduceType.AUTO.
            deep (bool, optional): If True (default), return a deep copy that is safe
                to mutate. Pass False to get the cached object directly for read-only
                use (avoids the copy cost).

        Returns:
            xr.Dataset: results in the form of an xarray dataset

        Note:
            Results are computed once and cached per instance. By default (``deep=True``)
            a deep copy is returned so callers can safely mutate the result. Internal
            hot paths pass ``deep=False`` to reuse the cached object directly.
        """
        cache_key = self._to_dataset_cache_key(reduce, result_var, level, agg_over_dims, agg_fn)
        if cache_key in self._to_dataset_cache:
            cached = self._to_dataset_cache[cache_key]
            return cached.copy(deep=True) if deep else cached

        reduce = self._resolve_auto(reduce)

        # Avoid an upfront copy for REDUCE/MINMAX — those reductions (.mean(),
        # .std(), .min(), .max()) always allocate new arrays, so the copy is
        # wasted.  SQUEEZE and NONE still need a copy because the returned
        # dataset may share memory with self.ds.
        ds_out = self.ds

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
                # For ResultBool: use binomial SE sqrt(p*(1-p)/n) instead of sample std
                n_repeats = ds_out.sizes["repeat"]
                for rv in self.bench_cfg.result_vars:
                    if isinstance(rv, ResultBool) and rv.name in ds_reduce_std.data_vars:
                        p = ds_reduce_mean[rv.name]
                        ds_reduce_std[rv.name] = np.sqrt(p * (1 - p) / n_repeats)
                # Assign std vars directly onto mean dataset (avoids xr.merge copy)
                for var in ds_reduce_std.data_vars:
                    ds_reduce_mean[f"{var}_std"] = ds_reduce_std[var]
                ds_out = ds_reduce_mean
            case ReduceType.MINMAX:  # TODO, need to pass mean, center of minmax, and minmax
                ds_reduce_mean = ds_out.mean(dim="repeat", keep_attrs=True)
                ds_reduce_min = ds_out.min(dim="repeat")
                ds_reduce_max = ds_out.max(dim="repeat")
                # Assign range vars directly onto mean dataset (avoids xr.merge copy)
                ds_range = ds_reduce_max - ds_reduce_min
                for var in ds_range.data_vars:
                    ds_reduce_mean[f"{var}_range"] = ds_range[var]
                ds_out = ds_reduce_mean
            case ReduceType.SQUEEZE:
                if (
                    self.bench_cfg.over_time
                    and "repeat" in ds_out.dims
                    and ds_out.sizes["repeat"] == 1
                ):
                    ds_out = ds_out.squeeze("repeat", drop=True).copy(deep=True)
                else:
                    ds_out = ds_out.squeeze(drop=True).copy(deep=True)
            case _:
                # ReduceType.NONE — deep copy for mutation safety
                ds_out = ds_out.copy(deep=True)

        # Optional aggregation across non-repeat dimensions (e.g., categorical)
        if agg_over_dims:
            # Only aggregate over dims that actually exist in the dataset
            dims_present = [d for d in agg_over_dims if d in ds_out.dims]
            if dims_present:
                # If some requested dims are missing, log an info for visibility
                missing = [d for d in agg_over_dims if d not in dims_present]
                if missing:
                    logging.info(
                        "Aggregation requested for dims %s but only found %s in dataset dims %s",
                        agg_over_dims,
                        dims_present,
                        list(ds_out.dims),
                    )

                # Support basic aggregations; default to mean
                fn = (agg_fn or "mean").lower()
                if fn == "sum":
                    ds_out = ds_out.sum(dim=dims_present, skipna=True)
                elif fn == "mean":
                    ds_agg_mean = ds_out.mean(dim=dims_present, skipna=True)
                    non_std_vars = [v for v in ds_out.data_vars if not v.endswith("_std")]
                    if non_std_vars:
                        ds_agg_std = ds_out[non_std_vars].std(dim=dims_present, skipna=True)
                        ds_agg_std = rename_ds(ds_agg_std, "std")
                        # Drop pre-existing _std vars that will be replaced by the
                        # aggregation std (e.g. from repeat reduction) to avoid merge conflicts.
                        expected_std = {f"{v}_std" for v in non_std_vars}
                        old_std = [v for v in ds_agg_mean.data_vars if v in expected_std]
                        if old_std:
                            ds_agg_mean = ds_agg_mean.drop_vars(old_std)
                        ds_out = xr.merge([ds_agg_mean, ds_agg_std])
                    else:
                        ds_out = ds_agg_mean
                elif fn == "max":
                    ds_out = ds_out.max(dim=dims_present, skipna=True)
                elif fn == "min":
                    ds_out = ds_out.min(dim=dims_present, skipna=True)
                elif fn == "median":
                    ds_out = ds_out.median(dim=dims_present, skipna=True)
                else:
                    # Fall back to mean if unknown string provided
                    ds_out = ds_out.mean(dim=dims_present, skipna=True)
            else:
                logging.warning(
                    "Aggregation requested for dims %s but none were found in dataset dims %s; returning unaggregated dataset",
                    agg_over_dims,
                    list(ds_out.dims),
                )
        if level is not None:
            coords_no_repeat = {}
            for c, v in ds_out.coords.items():
                if c != "repeat":
                    coords_no_repeat[c] = with_level(v.to_numpy(), level)
            ds_out = ds_out.sel(coords_no_repeat)
        self._to_dataset_cache[cache_key] = ds_out
        return ds_out.copy(deep=True) if deep else ds_out

    def get_optimal_vec(
        self,
        result_var: ParametrizedSweep,
        input_vars: list[ParametrizedSweep],
    ) -> list[Any]:
        """Get the optimal values from the sweep as a vector.

        Args:
            result_var (bn.ParametrizedSweep): Optimal values of this result variable
            input_vars (list[bn.ParametrizedSweep]): Define which input vars values are returned in the vector

        Returns:
            list[Any]: A vector of optimal values for the desired input vector
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
            result_var (bn.ParametrizedSweep): Optimal value of this result variable

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
    ) -> tuple[ParametrizedSweep, Any] | dict[ParametrizedSweep, Any]:
        """Get a list of tuples of optimal variable names and value pairs, that can be fed in as constant values to subsequent parameter sweeps

        Args:
            result_var (bn.ParametrizedSweep): Optimal values of this result variable
            keep_existing_consts (bool): Include any const values that were defined as part of the parameter sweep
            as_dict (bool): return value as a dictionary

        Returns:
            tuple[bn.ParametrizedSweep, Any]|[ParametrizedSweep, Any]: Tuples of variable name and optimal values
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

    def get_hmap(self, name: str | None = None):
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

    def get_results_var_list(self, result_var: ParametrizedSweep | None = None) -> list[Parameter]:
        return self.bench_cfg.result_vars if result_var is None else listify(result_var)

    def map_plots(
        self,
        plot_callback: Callable,
        result_var: ParametrizedSweep | None = None,
        row: EmptyContainer | None = None,
    ) -> pn.Row | None:
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
        plot_callback: Callable,
        hv_dataset: hv.Dataset = None,
        target_dimension: int = 2,
        result_var: ResultFloat | None = None,
        result_types=None,
        pane_collection: pn.pane = None,
        zip_results=False,
        reduce: ReduceType | None = None,
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ) -> pn.Row | None:
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(reduce=reduce)

        if pane_collection is None:
            pane_collection = pn.Row()

        row = EmptyContainer(pane_collection)

        # When any result variable has share_axis=False, enable axiswise so each
        # plot scales its y-axis independently instead of sharing a common range.
        active_rvs = [
            rv
            for rv in self.get_results_var_list(result_var)
            if result_types is None or isinstance(rv, result_types)
        ]
        needs_axiswise = any(not getattr(rv, "share_axis", True) for rv in active_rvs)

        base_cb = partial(plot_callback, **kwargs)
        axiswise_cb = base_cb

        if needs_axiswise:

            def _make_axiswise_cb(inner):
                def _axiswise_cb(**cb_kwargs):
                    result = inner(**cb_kwargs)
                    if result is not None:
                        if hasattr(result, "opts"):
                            return result.opts(axiswise=True)
                        if hasattr(result, "object") and hasattr(result.object, "opts"):
                            result.object = result.object.opts(axiswise=True)
                    return result

                return _axiswise_cb

            axiswise_cb = _make_axiswise_cb(base_cb)

        for rv in active_rvs:
            rv_dataset = hv_dataset
            if isinstance(rv, ResultBool) and "repeat" in hv_dataset.data.dims:
                non_repeat_dims = [d for d in hv_dataset.data.dims if d != "repeat"]
                if non_repeat_dims:
                    rv_dataset = self.to_hv_dataset(reduce=ReduceType.REDUCE)

            cb = axiswise_cb if needs_axiswise and not getattr(rv, "share_axis", True) else base_cb
            row.append(
                self.to_panes_multi_panel(
                    rv_dataset,
                    rv,
                    plot_callback=cb,
                    target_dimension=target_dimension,
                    pane_layout=pane_layout,
                )
            )

        if zip_results:
            return self.zip_results1D2(row.get())
        return row.get()

    def filter(
        self,
        plot_callback: Callable,
        plot_filter=None,
        float_range: VarRange | None = None,
        cat_range: VarRange | None = None,
        vector_len: VarRange | None = None,
        result_vars: VarRange | None = None,
        panel_range: VarRange | None = None,
        repeats_range: VarRange | None = None,
        input_range: VarRange | None = None,
        reduce: ReduceType = ReduceType.AUTO,
        target_dimension: int = 2,
        result_var: ResultFloat | None = None,
        result_types=None,
        pane_collection: pn.pane = None,
        override=False,
        hv_dataset: hv.Dataset | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: Literal["mean", "sum", "max", "min", "median"] = "mean",
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ) -> pn.panel | None:
        # Initialize default filters if not provided to avoid shared mutable defaults
        if float_range is None:
            float_range = VarRange(0, None)
        if cat_range is None:
            cat_range = VarRange(0, None)
        if vector_len is None:
            vector_len = VarRange(1, 1)
        if result_vars is None:
            result_vars = VarRange(1, 1)
        if panel_range is None:
            panel_range = VarRange(0, None)
        if repeats_range is None:
            repeats_range = VarRange(1, None)
        if input_range is None:
            input_range = VarRange(1, None)
        plot_filter = PlotFilter(
            float_range=float_range,
            cat_range=cat_range,
            vector_len=vector_len,
            result_vars=result_vars,
            panel_range=panel_range,
            repeats_range=repeats_range,
            input_range=input_range,
        )
        # When aggregating, adjust variable counts to reflect post-aggregation
        # dimensions so plot type filters correctly reject impossible combos
        # (e.g. curve with 0 kdims after collapsing all inputs).
        check_cfg = self.plt_cnt_cfg
        if agg_over_dims:
            agg_set = set(agg_over_dims)
            adj_float = [fv for fv in self.plt_cnt_cfg.float_vars if fv.name not in agg_set]
            adj_cat = [cv for cv in self.plt_cnt_cfg.cat_vars if cv.name not in agg_set]
            check_cfg = PltCntCfg(
                float_vars=adj_float,
                float_cnt=len(adj_float),
                cat_vars=adj_cat,
                cat_cnt=len(adj_cat),
                vector_len=self.plt_cnt_cfg.vector_len,
                result_vars=self.plt_cnt_cfg.result_vars,
                panel_vars=list(self.plt_cnt_cfg.panel_vars),
                panel_cnt=self.plt_cnt_cfg.panel_cnt,
                repeats=self.plt_cnt_cfg.repeats,
                inputs_cnt=len(adj_float) + len(adj_cat),
                print_debug=self.plt_cnt_cfg.print_debug,
            )
        matches_res = plot_filter.matches_result(check_cfg, callable_name(plot_callback), override)
        if matches_res.overall:
            # Compute aggregated dataset once (if requested) so all plotters benefit
            if hv_dataset is None:
                agg_dims = list(dict.fromkeys(agg_over_dims)) if agg_over_dims else None
                if agg_dims:
                    hv_dataset = self.to_hv_dataset(
                        reduce=reduce, agg_over_dims=agg_dims, agg_fn=agg_fn
                    )
            return self.map_plot_panes(
                plot_callback=plot_callback,
                hv_dataset=hv_dataset,
                target_dimension=target_dimension,
                result_var=result_var,
                result_types=result_types,
                pane_collection=pane_collection,
                reduce=reduce,
                pane_layout=pane_layout,
                **kwargs,
            )
        return matches_res.to_panel()

    def to_panes_multi_panel(
        self,
        hv_dataset: hv.Dataset,
        result_var: ResultFloat,
        plot_callback: Callable | None = None,
        target_dimension: int = 1,
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ):
        dims = len(hv_dataset.dimensions())
        # Exclude over_time from the dimension count used for layout decisions
        pane_dims = dims
        if (
            self.bench_cfg.over_time
            and "over_time" in list(hv_dataset.data.sizes)
            and hv_dataset.data.sizes["over_time"] > 1
        ):
            pane_dims = dims - 1
        if target_dimension is None:
            target_dimension = pane_dims
        return self._to_panes_da(
            hv_dataset.data,
            plot_callback=plot_callback,
            target_dimension=target_dimension,
            horizontal=pane_dims <= target_dimension + 1,
            result_var=result_var,
            pane_layout=pane_layout,
            **kwargs,
        )

    @staticmethod
    def _child_pane_layout(pane_layout: PaneLayout) -> PaneLayout:
        """Return the layout to use for child dimensions during recursion."""
        if pane_layout == PaneLayout.tabs_and_grid:
            return PaneLayout.grid
        return pane_layout

    def _iter_pane_slices(
        self, dataset, selected_dim, plot_callback, target_dimension, result_var, child_layout
    ):
        """Yield (label_val, panes) for each slice along selected_dim."""
        for i in range(dataset.sizes[selected_dim]):
            sliced = dataset.isel({selected_dim: i})
            label_val = sliced.coords[selected_dim].values.item()
            panes = self._to_panes_da(
                sliced,
                plot_callback=plot_callback,
                target_dimension=target_dimension,
                horizontal=len(sliced.sizes) <= target_dimension + 1,
                result_var=result_var,
                pane_layout=child_layout,
            )
            yield label_val, panes

    def _to_panes_da(
        self,
        dataset: xr.Dataset,
        plot_callback: Callable | None = None,
        target_dimension=1,
        horizontal=False,
        result_var=None,
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ) -> pn.panel:
        dims = list(d for d in dataset.sizes)

        # over_time is handled by hvplot's groupby widget, not pane recursion
        if self.bench_cfg.over_time and "over_time" in dims and dataset.sizes["over_time"] > 1:
            pane_dims = [d for d in dims if d != "over_time"]
        else:
            pane_dims = dims
        num_pane_dims = len(pane_dims)

        if num_pane_dims > target_dimension and num_pane_dims != 0:
            selected_dim = pane_dims[-1]
            depth = num_pane_dims - target_dimension - 1
            # Color is indexed by the position of the selected dim in the original
            # sweep (so each dim always gets the same tint across the grid), not by
            # recursion depth. Preserves the previous behavior.
            dim_color = color_tuple_to_css(int_to_col(num_pane_dims - 2, 0.05, 1.0))
            use_tabs = pane_layout in (PaneLayout.tabs, PaneLayout.tabs_and_grid)
            child_layout = self._child_pane_layout(pane_layout)
            slices = self._iter_pane_slices(
                dataset,
                selected_dim,
                plot_callback,
                target_dimension,
                result_var,
                child_layout,
            )

            if use_tabs:
                outer_container = ComposableContainerPanel(
                    name=" vs ".join(pane_dims),
                    background_col=dim_color,
                    compose_method=ComposeType.sequence,
                )
                for label_val, panes in slices:
                    label = ComposableContainerBase.label_formatter(selected_dim, label_val)
                    outer_container.append((label, panes))
            else:
                outer_container = ComposableContainerPanel(
                    name=" vs ".join(pane_dims),
                    background_col=dim_color,
                    compose_method=ComposeType.down if not horizontal else ComposeType.right,
                )
                max_label_chars = 0
                # For very long rows/columns, sprinkle extra label copies into
                # the content so the dim label stays visible when scrolled far
                # from the start.
                repeat_label_every = 5
                # Collect every label pane we create at this level so we can
                # apply uniform width in a single post-pass.
                level_labels: list[pn.pane.Markdown] = []
                # For dimension > 2 we inject the outer label into each inner
                # row/column of the content so it aligns row-for-row with the
                # inner dim's labels — and we SKIP the single centered bracket
                # label on inner_container (which would create a duplicate
                # outer column).  For dim <= 2 we keep the centered bracket
                # labels (simple 2D grids read best that way).
                inject_into_children = num_pane_dims > 2
                for label_val, panes in slices:
                    inner_container = ComposableContainerPanel(
                        name=outer_container.name,
                        nesting_depth=depth,
                        compose_method=ComposeType.down if horizontal else ComposeType.right,
                    )
                    label_text = ComposableContainerBase.label_formatter(selected_dim, label_val)
                    inner_container.append(panes)
                    if label_text is not None:
                        max_label_chars = max(max_label_chars, len(label_text))

                        injected = False
                        if inject_into_children and isinstance(panes, (pn.Row, pn.Column)):
                            for child in list(panes):
                                if isinstance(child, (pn.Row, pn.Column)):
                                    lead = make_label_pane(label_text)
                                    trail = make_label_pane(label_text)
                                    child.insert(0, lead)
                                    child.append(trail)
                                    level_labels.extend([lead, trail])
                                    injected = True

                        if not injected:
                            # Fallback for dim <= 2 (or when panes has no
                            # sub-layout children): single bracket labels on
                            # inner_container itself.
                            leading = make_label_pane(label_text)
                            trailing = make_label_pane(label_text)
                            inner_container.container.insert(0, leading)
                            inner_container.container.append(trailing)
                            level_labels.extend([leading, trailing])

                        # Every-N mid-interleave in the content for very wide
                        # or tall layouts (unchanged).
                        if (
                            isinstance(panes, (pn.Row, pn.Column))
                            and len(panes) > repeat_label_every
                        ):
                            insert_points = list(
                                range(repeat_label_every, len(panes), repeat_label_every)
                            )
                            for idx in reversed(insert_points):
                                mid = make_label_pane(label_text)
                                panes.insert(idx, mid)
                                level_labels.append(mid)
                    outer_container.append(inner_container.container)
                # Apply uniform width (in `ch` units) to every label we created
                # at this level so labels line up across slices.
                if max_label_chars > 0 and level_labels:
                    label_width = f"{max_label_chars + 2}ch"
                    for lbl in level_labels:
                        lbl.styles = {**lbl.styles, "width": label_width}
        else:
            # When over_time is active with >1 time points, the dataset still
            # contains the over_time dimension (it was excluded from pane recursion
            # so hvplot numeric plots can use groupby).  For pane-type results
            # (images, videos) we need to build a Panel slider manually because
            # they are not HoloViews objects and cannot use hv.HoloMap.
            if (
                self.bench_cfg.over_time
                and "over_time" in list(dataset.sizes)
                and dataset.sizes["over_time"] > 1
                and isinstance(result_var, (ResultVideo, ResultImage, ResultRerun))
            ):
                if isinstance(result_var, ResultRerun):
                    return self._pane_over_time_grid(dataset, result_var)
                return self._pane_over_time_slider(dataset, result_var)
            return plot_callback(dataset=dataset, result_var=result_var, **kwargs)

        return outer_container.render()

    def _pane_over_time_slider(
        self,
        dataset: xr.Dataset,
        result_var,
    ) -> pn.Column:
        """Create a Panel slider widget for over_time with pane-type results.

        Numeric plot callbacks (line, heatmap) handle over_time internally via
        hv.HoloMap.  Pane-type callbacks (images, videos, rerun) cannot use
        HoloMap because they produce Panel objects, not HoloViews elements.
        This method builds per-time-point content and swaps it via a Bokeh JS
        callback to avoid Panel's ImportedStyleSheet document-ownership errors.
        """
        import base64
        from bokeh.models import CustomJS, Div
        from bokeh.models.widgets import Slider as BokehSlider

        time_vals = list(dataset.coords["over_time"].values)
        over_time_dtype = dataset.coords["over_time"].dtype
        is_datetime = np.issubdtype(over_time_dtype, np.datetime64)
        labels = [str(pd.to_datetime(t)) if is_datetime else str(t) for t in time_vals]

        is_rerun = isinstance(result_var, ResultRerun)
        is_video = isinstance(result_var, ResultVideo)

        if is_rerun:
            from bencher.utils_rrd import rrd_file_to_pane

        _NO_DATA_HTML = (
            '<div style="background:#eee;padding:20px;text-align:center;color:#999">'
            "No data for this time point</div>"
        )
        html_list = []
        for idx, _t in enumerate(time_vals):
            ds_t = dataset.isel(over_time=idx)
            filepath = str(self.zero_dim_da_to_val(ds_t[result_var.name]))
            if filepath == "NAN" or not os.path.isfile(filepath):
                html_list.append(_NO_DATA_HTML)
                continue
            if is_rerun:
                pane = rrd_file_to_pane(filepath, width=result_var.width, height=result_var.height)
                html_list.append(pane.object)
            else:
                mime = "video/mp4" if is_video else "image/png"
                with open(filepath, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                if is_video:
                    html_list.append(
                        f'<video controls src="data:{mime};base64,{b64}" style="background:white"/>'
                    )
                else:
                    html_list.append(
                        f'<img src="data:{mime};base64,{b64}" style="background:white"/>'
                    )

        # Pure Bokeh Div + Slider with a JS callback — no Panel pane updates,
        # so no ImportedStyleSheet sharing across documents.
        default_idx = len(time_vals) - 1
        div = Div(text=html_list[default_idx])
        bokeh_slider = BokehSlider(
            start=0,
            end=len(time_vals) - 1,
            value=default_idx,
            step=1,
            title=f"over_time: {labels[default_idx]}",
        )
        callback = CustomJS(
            args=dict(div=div, html_list=html_list, labels=labels, slider=bokeh_slider),
            code=(
                "div.text = html_list[slider.value];"
                " slider.title = 'over_time: ' + labels[slider.value];"
            ),
        )
        bokeh_slider.js_on_change("value", callback)

        return pn.Column(pn.pane.Bokeh(div), pn.pane.Bokeh(bokeh_slider))

    def _pane_over_time_grid(
        self,
        dataset: xr.Dataset,
        result_var,
    ) -> pn.Row | pn.pane.Markdown:
        """Render over_time pane results as a grid of labelled panels.

        Used for ResultRerun because rerun iframes do not work inside a
        Bokeh JS slider swap (the viewer fails to re-initialise).
        """
        from bencher.utils_rrd import rrd_file_to_pane

        time_vals = list(dataset.coords["over_time"].values)
        over_time_dtype = dataset.coords["over_time"].dtype
        is_datetime = np.issubdtype(over_time_dtype, np.datetime64)
        labels = [str(pd.to_datetime(t)) if is_datetime else str(t) for t in time_vals]

        items = []
        for idx, label in enumerate(labels):
            ds_t = dataset.isel(over_time=idx)
            filepath = str(self.zero_dim_da_to_val(ds_t[result_var.name]))
            if filepath == "NAN" or not os.path.isfile(filepath):
                continue
            pane = rrd_file_to_pane(filepath, width=result_var.width, height=result_var.height)
            items.append(pn.Column(pn.pane.Markdown(f"**{label}**"), pane))

        if not items:
            return pn.pane.Markdown("*No rerun data available*")
        return pn.Row(*items)

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
        include_types: list[type] | None = None,
        exclude_names: list[str] | None = None,
    ) -> xr.Dataset:
        """Given a dataset, return a reduced dataset that only contains data from a specified level.  By default all types of variables are filtered at the specified level.  If you only want to get a reduced level for some types of data you can pass in a list of types to get filtered, You can also pass a list of variables names to exclude from getting filtered
        Args:
            dataset (xr.Dataset): dataset to filter
            level (int): desired data resolution level
            include_types (list[type], optional): Only filter data of these types. Defaults to None.
            exclude_names (list[str], optional): Only filter data with these variable names. Defaults to None.

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

    def to_title(self, panel_name: str | None = None) -> pn.pane.Markdown:
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
