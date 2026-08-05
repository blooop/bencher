from __future__ import annotations

import inspect
import logging
import os
from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from enum import Enum, auto
from functools import partial
from textwrap import wrap
from typing import Any, Literal, assert_never

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
import xarray as xr
from param import Parameter

from bencher.bench_cfg import BenchCfg
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.plotting.plt_cnt_cfg import PltCntCfg
from bencher.results.composable_container.composable_container_base import (
    ComposableContainerBase,
    ComposeType,
    PaneLayout,
)
from bencher.results.composable_container.composable_container_panel import (
    ComposableContainerPanel,
)
from bencher.utils import (
    AggFn,
    callable_name,
    color_tuple_to_css,
    int_to_col,
    listify,
    normalize_agg_fn,
)
from bencher.variables.inputs import with_subsampling_divisions
from bencher.variables.parametrised_sweep import ParametrizedSweep
from bencher.variables.results import (
    PANEL_TYPES,
    OptDir,
    ResultBool,
    ResultDataSet,
    ResultFloat,
    ResultImage,
    ResultReference,
    ResultRerun,
    ResultVideo,
    result_is_missing,
)

logger = logging.getLogger(__name__)

# Shared defaults for BenchResultBase.filter(). VarRange is frozen, so a single
# instance can back every call; module-level names also keep ruff's B008 happy.
_ANY_COUNT = VarRange.unbounded()
_AT_LEAST_ONE = VarRange.at_least(1)

# todo add plugins
# https://gist.github.com/dorneanu/cce1cd6711969d581873a88e0257e312
# https://kaleidoescape.github.io/decorated-plugins/


class ReduceType(Enum):
    AUTO = auto()  # automatically determine the best way to reduce the dataset
    SQUEEZE = auto()  # remove any dimensions of length 1
    REDUCE = auto()  # get the mean and std dev of the data along the "repeat" dimension
    MINMAX = auto()  # get the minimum and maximum of data along the "repeat" dimension
    NONE = auto()  # don't reduce


# ReduceType with AUTO excluded: the return type of _resolve_auto, so that the match in
# to_dataset is exhaustive over four members rather than relying on a catch-all.
#
# P1's caveat here is now DISCHARGED: plan 23 P12 enabled `invalid-return-type`, which is
# the rule that checks _resolve_auto really returns a member of this Literal. The proof is
# therefore complete at check time in both directions -- verified by seeding
# `return ReduceType.AUTO` on the `None` path, which ty rejects with
# `expected Literal[SQUEEZE, REDUCE, MINMAX, NONE], found Literal[ReduceType.AUTO]`.
# Adding a ReduceType member without updating both this alias and the match now fails
# `pixi run ty` rather than at runtime in assert_never.
ResolvedReduceType = Literal[
    ReduceType.SQUEEZE, ReduceType.REDUCE, ReduceType.MINMAX, ReduceType.NONE
]


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


def _accepts_keyword(callback: Callable, name: str) -> bool:
    """True when *callback* can be called with the *name* keyword.

    ``plot_callback`` is a public extension point: a caller may pass any callable
    to ``map_plot_panes``, including one whose signature is exactly
    ``(dataset, result_var)``.  Render-internal keywords must therefore be
    offered rather than imposed — a callback that does not declare the keyword
    (and has no ``**kwargs`` to absorb it) is called the way it always was
    instead of raising ``TypeError``.  Uninspectable callables (C builtins) are
    treated as not accepting it, which is the safe direction.
    """
    try:
        params = inspect.signature(callback).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


class BenchResultBase:
    def __init__(self, bench_cfg: BenchCfg) -> None:
        self.bench_cfg = bench_cfg
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
        self.plt_cnt_cfg = PltCntCfg.generate_plt_cnt_cfg(self.bench_cfg, self.ds)
        self.bench_cfg = self.wrap_long_time_labels(self.bench_cfg)
        self.ds = convert_dataset_bool_dims_to_str(self.ds)
        self._to_dataset_cache.clear()

    def result_samples(self) -> int:
        """The number of values recorded, for the most-populated data variable.

        This counts *cells*, not sweep points: the repeat dimension multiplies it, so a
        two-point sweep at ``repeats=3`` reports 6. Returns 0 for a dataset with no data
        variables.

        Max across data variables, rather than sum or first:

        - sum would double-count -- two result variables over two samples is 2, not 4;
        - first would undercount a sweep whose other variables partly failed, since a
          failed sample leaves a NaN that ``count()`` skips.
        """
        counts = self.ds.count()
        return max((int(counts[name].values) for name in counts.data_vars), default=0)

    def to_hv_dataset(
        self,
        reduce: ReduceType | None = ReduceType.AUTO,
        result_var: ResultFloat | None = None,
        subsampling_divisions: int | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: AggFn | str | None = None,
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
                subsampling_divisions=subsampling_divisions,
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
                subsampling_divisions=subsampling_divisions,
                agg_over_dims=agg_over_dims,
                agg_fn=agg_fn,
                deep=False,
            )
        )

    def _resolve_auto(self, reduce: ReduceType | None) -> ResolvedReduceType:
        """Resolve AUTO (and the legacy `None` sentinel) to a concrete ReduceType.

        `reduce=None` reaches here from public methods that declare
        `reduce: ReduceType | None` and forward it unchanged (`map_plot_panes`,
        `filter`, ...). It has always meant "no reduction": it used to fall through
        `to_dataset`'s catch-all arm. Mapping it *here* rather than at the callers
        matters, because `to_hv_dataset` branches on `reduce == ReduceType.NONE`
        beforehand and `None` deliberately does not match that, which preserves the
        unit-carrying kdims of its generic arm.

        NOTE (plan 23): `None` and `AUTO` meaning different things on one field is the
        sentinel smell this plan exists to remove, and `map_plot_panes` defaulting to
        "no reduction" disagrees with `to_hv_dataset`'s AUTO. Both are behaviour changes
        that need a phase which can own them.
        """
        if reduce is None:
            return ReduceType.NONE
        if reduce is ReduceType.AUTO:
            return ReduceType.REDUCE if self.bench_cfg.repeats > 1 else ReduceType.SQUEEZE
        return reduce

    def _to_dataset_cache_key(
        self,
        reduce: ReduceType,
        result_var: ResultFloat | str | None,
        subsampling_divisions: int | None,
        agg_over_dims: list[str] | None,
        agg_fn: AggFn | str | None,
    ) -> tuple:
        """Build a hashable cache key from normalized to_dataset() arguments.

        Raises:
            ValueError: If ``agg_fn`` is outside the ``AggFn`` vocabulary. Validating
                here is deliberate and load-bearing, not a side effect of key building:
                ``to_dataset`` returns on a cache hit before reaching its ``match``, so
                this is the only ``agg_fn`` check on the warm-cache path.
        """
        reduce = self._resolve_auto(reduce)
        rv_key = result_var.name if isinstance(result_var, Parameter) else result_var
        # Normalize dimension order so aggregation over the same set shares cache entries
        dims_key = tuple(sorted(agg_over_dims)) if agg_over_dims else None
        # Validate unconditionally, even though the *key* only needs fn when there are
        # agg dims (without them aggregation is skipped entirely, so every fn collapses
        # to the same dataset — hence the None below, which keeps those calls sharing one
        # cache entry). Gating the *validation* on agg_over_dims would make an unknown
        # agg_fn raise or not depending on the data ("does this dim exist in the
        # dataset?"), which is exactly the data-dependent validation plan 23 exists to
        # remove. normalize_agg_fn is cheap, idempotent and total (None -> MEAN).
        fn = normalize_agg_fn(agg_fn)
        fn_key = fn if agg_over_dims else None
        return (reduce, rv_key, subsampling_divisions, dims_key, fn_key)

    def to_dataset(
        self,
        reduce: ReduceType | None = ReduceType.AUTO,
        result_var: ResultFloat | str | None = None,
        subsampling_divisions: int | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: AggFn | str | None = None,
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
        # NOTE: this call validates agg_fn (normalize_agg_fn, inside), and that is
        # load-bearing rather than redundant with the match further down: on a cache
        # hit we return two lines below and never reach the match, so this is the
        # *only* validation on the warm-cache path. Do not "optimize" it away.
        cache_key = self._to_dataset_cache_key(
            reduce, result_var, subsampling_divisions, agg_over_dims, agg_fn
        )
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
                ds_reduce_mean = ds_out.mean(dim="repeat", skipna=True, keep_attrs=True)
                ds_reduce_std = ds_out.std(dim="repeat", skipna=True, keep_attrs=False)
                # For ResultBool: use binomial SE sqrt(p*(1-p)/n) instead of sample std.
                # n is the per-cell count of *valid* (non-NaN) repeats, not the full
                # repeat dim size: NaN is the "missing" sentinel (see ResultBool /
                # ResultFloat.__init__) and p above is a skipna mean, so dividing by the
                # full dim size would understate the SE when any repeat is missing.
                for rv in self.bench_cfg.result_vars:
                    if isinstance(rv, ResultBool) and rv.name in ds_reduce_std.data_vars:
                        p = ds_reduce_mean[rv.name]
                        n_valid = ds_out[rv.name].notnull().sum(dim="repeat")
                        ds_reduce_std[rv.name] = np.sqrt(p * (1 - p) / n_valid)
                # Assign std vars directly onto mean dataset (avoids xr.merge copy)
                for var in ds_reduce_std.data_vars:
                    ds_reduce_mean[f"{var}_std"] = ds_reduce_std[var]
                ds_out = ds_reduce_mean
            case ReduceType.MINMAX:  # TODO, need to pass mean, center of minmax, and minmax
                ds_reduce_mean = ds_out.mean(dim="repeat", skipna=True, keep_attrs=True)
                ds_reduce_min = ds_out.min(dim="repeat", skipna=True)
                ds_reduce_max = ds_out.max(dim="repeat", skipna=True)
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
            case ReduceType.NONE:
                # deep copy for mutation safety
                ds_out = ds_out.copy(deep=True)
            case _ as unreachable:
                assert_never(unreachable)

        # Optional aggregation across non-repeat dimensions (e.g., categorical)
        if agg_over_dims:
            # Only aggregate over dims that actually exist in the dataset
            dims_present = [d for d in agg_over_dims if d in ds_out.dims]
            if dims_present:
                # If some requested dims are missing, log an info for visibility
                missing = [d for d in agg_over_dims if d not in dims_present]
                if missing:
                    logger.info(
                        "Aggregation requested for dims %s but only found %s in dataset dims %s",
                        agg_over_dims,
                        dims_present,
                        list(ds_out.dims),
                    )

                # Normalize at the boundary (raises on an unknown value — no more
                # silent fall-back to mean), then match exhaustively (plan 24 A2/A3).
                # This is the second normalize_agg_fn call on this path (the first is in
                # _to_dataset_cache_key above) and both are needed: that one is the only
                # validation when the cache hits and this one is the only thing that
                # gives the match subject a type ty can check. Neither substitutes for
                # the other; the function is idempotent, so calling it twice is free.
                match normalize_agg_fn(agg_fn):
                    case AggFn.MEAN:
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
                    case AggFn.SUM:
                        ds_out = ds_out.sum(dim=dims_present, skipna=True)
                    case AggFn.MAX:
                        ds_out = ds_out.max(dim=dims_present, skipna=True)
                    case AggFn.MIN:
                        ds_out = ds_out.min(dim=dims_present, skipna=True)
                    case AggFn.MEDIAN:
                        ds_out = ds_out.median(dim=dims_present, skipna=True)
                    case _ as unreachable:
                        assert_never(unreachable)
            else:
                logger.warning(
                    "Aggregation requested for dims %s but none were found in dataset dims %s; returning unaggregated dataset",
                    agg_over_dims,
                    list(ds_out.dims),
                )
        if subsampling_divisions is not None:
            coords_no_repeat = {}
            for c, v in ds_out.coords.items():
                if c != "repeat":
                    coords_no_repeat[c] = with_subsampling_divisions(
                        v.to_numpy(), subsampling_divisions
                    )
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
                logger.warning(f"values size: {da.coords[iv.name].values.size}")
                output.append(max(da.coords[iv.name].values[()]))
            logger.info(f"Maximum value of {iv.name}: {output[-1]}")
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
        logger.info(f"optimal value of {result_var.name}: {opt_val.values}")
        return indices

    def get_optimal_inputs(
        self,
        result_var: ParametrizedSweep,
        keep_existing_consts: bool = True,
        as_dict: bool = False,
    ) -> list[tuple[Parameter, Any]] | dict[Parameter, Any]:
        """Get a list of tuples of optimal variable names and value pairs, that can be fed in as constant values to subsequent parameter sweeps

        Args:
            result_var (bn.ParametrizedSweep): Optimal values of this result variable
            keep_existing_consts (bool): Include any const values that were defined as part of the parameter sweep
            as_dict (bool): return value as a dictionary

        Returns:
            A list of ``(input_var, optimal_value)`` pairs, or that same mapping as a
            dict when ``as_dict``. The keys are ``param.Parameter`` descriptors, not
            ``ParametrizedSweep`` instances.
        """
        da = self.get_optimal_value_indices(result_var)
        if keep_existing_consts:
            # `or []`: const_vars is a param List, so it reads as `list | None`.
            output = deepcopy(self.bench_cfg.const_vars) or []
        else:
            output = []

        for iv in self.bench_cfg.input_vars:
            # assert da.coords[iv.name].values.size == (1,)
            if da.coords[iv.name].values.size == 1:
                # https://stackoverflow.com/questions/773030/why-are-0d-arrays-in-numpy-not-considered-scalar
                # use [()] to convert from a 0d numpy array to a scalar
                output.append((iv, da.coords[iv.name].values[()]))
            else:
                logger.warning(f"values size: {da.coords[iv.name].values.size}")
                output.append((iv, max(da.coords[iv.name].values[()])))

            logger.info(f"Maximum value of {iv.name}: {output[-1][1]}")
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

        # xarray types dimension names as `Hashable`, not `str`, and both `DataArray.name`
        # and `Parameter.name` are optional. `str()` is the identity on everything bencher
        # actually produces here. Where it is not -- an unnamed DataArray -- this now
        # renders "None" in a plot title instead of aborting the report build with
        # `TypeError: sequence item 0: expected str instance, NoneType found`, which is
        # the right trade for a display string.
        if isinstance(dataset, xr.DataArray):
            tit = [str(dataset.name), *(str(d) for d in dataset.dims)]
        else:
            tit = [str(result_var.name), *(str(d) for d in dataset.sizes)]

        return " vs ".join(tit)

    def get_results_var_list(self, result_var: ParametrizedSweep | None = None) -> list[Parameter]:
        if result_var is None:
            # `or []`: result_vars is a param List, so it reads as `list | None`.
            return self.bench_cfg.result_vars or []
        # `or []` because listify returns None for a None input; unreachable here given
        # the branch above, but the annotation has to hold without that reasoning.
        return listify(result_var) or []

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
            for a1 in range(len(a)):
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

    def map_sample_panes(
        self,
        result_types,
        container: Callable | None = None,
        result_var: Parameter | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        subsampling_divisions: int | None = None,
        **kwargs,
    ) -> pn.pane.panel | None:
        """One pane per sample of every result whose type is in *result_types*.

        The single place the per-sample render path is spelled out: squeeze to one
        value per sample, then map ``ds_to_container`` (which applies *container*,
        the per-sample container, or the one declared on the result var) over each.
        Callers differ only in which result types they claim — ``result_types`` is
        the parameter rather than a subclass hook so a renderer can be a plain
        function over any result object.
        """
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(
                ReduceType.SQUEEZE, subsampling_divisions=subsampling_divisions
            )
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)
        return self.map_plot_panes(
            partial(self.ds_to_container, container=container),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=result_types,
            **kwargs,
        )

    def map_plot_panes(
        self,
        plot_callback: Callable,
        hv_dataset: hv.Dataset | None = None,
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
        float_range: VarRange = _ANY_COUNT,
        cat_range: VarRange = _ANY_COUNT,
        panel_range: VarRange = _ANY_COUNT,
        repeats_range: VarRange = _AT_LEAST_ONE,
        input_range: VarRange = _AT_LEAST_ONE,
        reduce: ReduceType = ReduceType.AUTO,
        target_dimension: int = 2,
        result_var: ResultFloat | None = None,
        result_types=None,
        pane_collection: pn.pane = None,
        override=False,
        hv_dataset: hv.Dataset | None = None,
        agg_over_dims: list[str] | None = None,
        agg_fn: AggFn | str = AggFn.MEAN,
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ) -> pn.panel | None:
        # VarRange is frozen, so these defaults are safe to share between calls.
        plot_filter = PlotFilter(
            float_range=float_range,
            cat_range=cat_range,
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
                panel_vars=list(self.plt_cnt_cfg.panel_vars),
                panel_cnt=self.plt_cnt_cfg.panel_cnt,
                repeats=self.plt_cnt_cfg.repeats,
                inputs_cnt=len(adj_float) + len(adj_cat),
                # signature facts carry over; cat_levels drops the collapsed dims
                # to stay consistent with adj_cat
                has_time=self.plt_cnt_cfg.has_time,
                time_steps=self.plt_cnt_cfg.time_steps,
                result_kinds=dict(self.plt_cnt_cfg.result_kinds),
                cat_levels={
                    name: levels
                    for name, levels in self.plt_cnt_cfg.cat_levels.items()
                    if name not in agg_set
                },
                samples_per_point=self.plt_cnt_cfg.samples_per_point,
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
            prev_cfg = self.plt_cnt_cfg
            if agg_over_dims:
                self.plt_cnt_cfg = check_cfg
            try:
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
            finally:
                self.plt_cnt_cfg = prev_cfg
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
        plot_callback: Callable,
        target_dimension=1,
        horizontal=False,
        result_var=None,
        pane_layout: PaneLayout = PaneLayout.grid,
        **kwargs,
    ) -> pn.panel:
        # str(), because xarray types dim names as `Hashable`: these feed both
        # `dataset.sel()` (which takes either) and the container `name=` strings below.
        dims = [str(d) for d in dataset.sizes]

        # over_time is handled by hvplot's groupby widget, not pane recursion
        if self.bench_cfg.over_time and "over_time" in dims and dataset.sizes["over_time"] > 1:
            pane_dims = [d for d in dims if d != "over_time"]
        else:
            pane_dims = dims
        num_pane_dims = len(pane_dims)

        if num_pane_dims > target_dimension and num_pane_dims != 0:
            selected_dim = pane_dims[-1]
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
                max_len = 0
                for label_val, panes in slices:
                    inner_container = ComposableContainerPanel(
                        name=outer_container.name,
                        width=num_pane_dims - target_dimension,
                        var_name=selected_dim,
                        var_value=label_val,
                        compose_method=ComposeType.down if horizontal else ComposeType.right,
                    )
                    max_len = max(max_len, inner_container.label_len)
                    inner_container.append(panes)
                    outer_container.append(inner_container.container)
                for c in outer_container.container:
                    c[0].width = max_len * 7
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
            ):
                if isinstance(result_var, ResultRerun):
                    return self._pane_over_time_grid(dataset, result_var)
                if isinstance(result_var, (ResultVideo, ResultImage)):
                    return self._pane_over_time_slider(dataset, result_var)
                if isinstance(result_var, PANEL_TYPES):
                    # Every *other* pane type renders one labelled pane per time
                    # point.  Catching the whole family rather than listing members
                    # is the point: for these, the fall-through below is not a
                    # different layout, it is a crash — it hands `plot_callback` a
                    # dataset that still carries over_time, and a per-sample
                    # renderer asking that for one value raises. A pane type
                    # without a bespoke over_time layout must still get a correct
                    # one, including one added after this line was written.
                    # Per-type concerns (ResultDataSet's legacy index cells) belong
                    # to the layout, not to this branch — see the method's docstring.
                    return self._pane_over_time_samples(
                        dataset, result_var, plot_callback, **kwargs
                    )
                # Numeric callbacks (line, bar, heatmap) are the ones that *must*
                # keep the whole over_time dimension: they build the slider
                # themselves via hvplot groupby / hv.HoloMap, and pre-selecting a
                # time point here would flatten the series they exist to show.
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
            filepath = self._over_time_filepath(dataset, result_var, idx)
            if filepath is None:
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
            args={"div": div, "html_list": html_list, "labels": labels, "slider": bokeh_slider},
            code=(
                "div.text = html_list[slider.value];"
                " slider.title = 'over_time: ' + labels[slider.value];"
            ),
        )
        bokeh_slider.js_on_change("value", callback)

        return pn.Column(pn.pane.Bokeh(div), pn.pane.Bokeh(bokeh_slider))

    def _over_time_filepath(self, dataset: xr.Dataset, result_var, idx: int) -> str | None:
        """Resolve the on-disk filepath for a file-backed result var at an over_time index.

        Returns None when the entry is missing/unrecorded (per ``result_is_missing``)
        or when the stored path does not point at an existing file.
        """
        ds_t = dataset.isel(over_time=idx)
        value = self.zero_dim_da_to_val(ds_t[result_var.name])
        if result_is_missing(result_var, value):
            return None
        filepath = str(value)
        if not os.path.isfile(filepath):
            return None
        return filepath

    def _pane_over_time_grid(
        self,
        dataset: xr.Dataset,
        result_var,
    ) -> pn.Row | pn.pane.Markdown:
        """Render over_time pane results as a grid of labelled panels.

        Used for ResultRerun because rerun iframes do not work inside a
        Bokeh JS slider swap (the viewer fails to re-initialise).

        A container declared on the result var wins over the rerun viewer, the
        same way it does on the single-run path in ``ds_to_container``: a renderer
        that only applied while history was off would draw one thing on the first
        run and something else on the second.
        """
        time_vals = list(dataset.coords["over_time"].values)
        over_time_dtype = dataset.coords["over_time"].dtype
        is_datetime = np.issubdtype(over_time_dtype, np.datetime64)
        labels = [str(pd.to_datetime(t)) if is_datetime else str(t) for t in time_vals]

        render = self.declared_container(result_var)
        if render is None:
            # Imported only when it is actually the renderer, so a declared
            # container does not drag in the rerun viewer stack.
            from bencher.utils_rrd import rrd_file_to_pane

            render = partial(rrd_file_to_pane, width=result_var.width, height=result_var.height)

        items = []
        for idx, label in enumerate(labels):
            filepath = self._over_time_filepath(dataset, result_var, idx)
            if filepath is None:
                continue
            items.append(pn.Column(pn.pane.Markdown(f"**{label}**"), render(filepath)))

        if not items:
            return pn.pane.Markdown("*No rerun data available*")
        return pn.Row(*items)

    def _pane_over_time_samples(
        self,
        dataset: xr.Dataset,
        result_var,
        plot_callback: Callable,
        **kwargs,
    ) -> pn.Row | None:
        """Render a pane-typed result over_time as a row of labelled per-time panes.

        The general over_time layout for pane types, and the only one that reduces
        the dimension before the per-sample renderer sees it: it selects one time
        index at a time, so ``plot_callback`` is handed the single value its
        contract is written for. ``ResultRerun`` and ``ResultVideo``/
        ``ResultImage`` opt out into layouts of their own; every other pane type
        arrives here, including any added later.

        A time point whose value is missing is skipped, so a variable that a
        historical run did not record leaves a gap rather than a broken pane.

        For ``ResultDataSet``, path-backed cells are meaningful in any process, so
        history points render instead of being cut down to the latest event (the
        pre-plan-22 ``isel(over_time=-1)`` workaround). A legacy index cell is only
        trusted at the *final* time index: ``dataset_list`` holds the final run's
        payloads alone, so a pre-plan history with in-range indices at every time
        point would otherwise render the current payload under historical labels.
        Untrusted legacy cells render as a labelled placeholder instead.

        ``legacy_trusted`` is only *offered* to *plot_callback*: it is a
        render-internal keyword, and ``plot_callback`` is a public extension
        point that a caller may satisfy with a plain ``(dataset, result_var)``
        function.  Passing it unconditionally would turn such a callback into a
        ``TypeError`` the moment its result went over_time, so a callback that
        cannot name it is called exactly as it was before this path existed.
        """
        time_vals = list(dataset.coords["over_time"].values)
        is_datetime = np.issubdtype(dataset.coords["over_time"].dtype, np.datetime64)
        labels = [str(pd.to_datetime(t)) if is_datetime else str(t) for t in time_vals]

        pass_trust = _accepts_keyword(plot_callback, "legacy_trusted")
        items = []
        final_idx = len(labels) - 1
        for idx, label in enumerate(labels):
            trust_kwargs = {"legacy_trusted": idx == final_idx} if pass_trust else {}
            pane = plot_callback(
                dataset=dataset.isel(over_time=idx),
                result_var=result_var,
                **trust_kwargs,
                **kwargs,
            )
            if pane is None:
                continue
            items.append(pn.Column(pn.pane.Markdown(f"**{label}**"), pane))

        if not items:
            return None
        return pn.Row(*items)

    def zero_dim_da_to_val(self, da_ds: xr.DataArray | xr.Dataset) -> Any:
        # todo this is really horrible, need to improve
        dim = None
        if isinstance(da_ds, xr.Dataset):
            dim = next(iter(da_ds.keys()))
            da = da_ds[dim]
        else:
            da = da_ds

        # Callers hand this a single point, so collapse any length-1 dimension it
        # still carries; keep the coordinates, they are what expand_dims below uses.
        if any(size == 1 for size in da.sizes.values()):
            da = da.squeeze(drop=False)

        # expand_dims needs a name that is not a dimension yet.  Picking one that is
        # still live raises "Dimension <name> already exists", which points at the
        # coordinate rather than at the caller that failed to reduce it.
        for k in da.coords:
            if k not in da.dims:
                dim = k
                break
        if dim is None or dim in da.dims:
            return da.values.squeeze().item()
        return da.expand_dims(dim).values[0]

    @staticmethod
    def _unreduced_dims(da: xr.DataArray) -> dict[str, int]:
        """Dimensions of a supposedly-single point that still hold several values."""
        return {str(d): int(da.sizes[d]) for d in da.dims if da.sizes[d] > 1}

    @staticmethod
    def declared_container(*sources: Any) -> Any:
        """The first container declared by *sources*, in the order given.

        A "declared" container is the single-argument renderer a result variable
        carries: attached to one stored sample inside ``benchmark()``, or declared
        once on the class. It is distinct from the ``container=`` a *renderer* passes
        in, which is a panel pane constructor and takes styling keywords — see
        :meth:`ds_to_container`.

        ``getattr``, not attribute access: a result pickled before a type gained the
        slot unpickles without it, and reports of old runs still have to render.
        """
        for source in sources:
            candidate = getattr(source, "container", None) if source is not None else None
            if candidate is not None:
                return candidate
        return None

    def _dataset_sample_to_container(  # pylint: disable=too-many-return-statements
        self, val: Any, result_var: Parameter, container, legacy_trusted: bool = True
    ) -> Any:
        """Render one stored ``ResultDataSet`` cell, whichever generation stored it.

        Three cell shapes exist (plan 22, D3):

        1. a ``str`` blob reference (collected after plan 22) — a content-hash
           name, or an absolute path from a cache dir collected before names
           became the cell format; either resolves through ``load_blob``, which
           looks in the *active* cache dir first so a cache tarred on one machine
           and restored at another path still renders, then in the cache dir this
           result recorded at collect time so rendering from a different working
           directory than the sweep ran in still finds them.  A payload materialized
           with a per-sample container is a pickled ``ResultDataSet`` wrapper, so
           the full precedence chain (renderer-supplied → sample's → class's →
           raw object) still applies; a blob that cannot be loaded (deleted,
           corrupt) renders as a labelled placeholder — never a crash;
        2. an ``int`` index (a result pickled or cached before plan 22) — looked
           up in ``dataset_list`` when this result still carries the list that
           produced it *and* the cell is trusted (see below), and rendered as a
           labelled placeholder otherwise (an old cell without its list is
           honestly unrecoverable — never a crash);
        3. the missing sentinel of either generation (``"NAN"`` / ``-1``) →
           ``None``, which pane composition skips.

        ``legacy_trusted`` guards the over_time case: ``dataset_list`` holds only
        the *final* run's payloads, so a legacy int at a historical time index is
        in range yet points at the wrong run's payload.  The over_time render
        path passes ``legacy_trusted=False`` for every non-final time index;
        every other call site keeps the default ``True``.
        """
        if result_is_missing(result_var, val):
            return None
        if isinstance(val, str):
            from bencher.blob_store import blob_cache_dir_hints, load_blob

            try:
                payload = load_blob(val, fallback_cache_dirs=blob_cache_dir_hints(self.ds))
            except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.warning(
                    "ResultDataSet '%s': failed to load blob %r (%s: %s)",
                    result_var.name,
                    val,
                    type(exc).__name__,
                    exc,
                )
                return pn.pane.Markdown(
                    f"*'{result_var.name}': stored blob could not be loaded; "
                    "see the log for the locations tried*"
                )
            sample = payload if isinstance(payload, ResultDataSet) else None
            if sample is not None:
                payload = sample.obj
            # Renderer-supplied container wins, then the sample's, then the class's.
            resolved = container or self.declared_container(sample, result_var)
            return resolved(payload) if resolved is not None else payload
        # Legacy int cell.  Over_time concat can promote the old int column to
        # float, so integral floats are legacy indices too.
        try:
            idx = int(val)
        except (TypeError, ValueError):
            logger.warning(
                "ResultDataSet '%s': unrecognised cell %r (neither a blob reference nor a legacy index)",
                result_var.name,
                val,
            )
            return pn.pane.Markdown(
                f"*'{result_var.name}': stored cell is not renderable ({type(val).__name__})*"
            )
        if not legacy_trusted:
            logger.warning(
                "ResultDataSet '%s': legacy cell %r at a historical time point; "
                "dataset_list only holds the final run's payloads, so the "
                "historical payload is unrecoverable",
                result_var.name,
                val,
            )
            return pn.pane.Markdown(
                f"*'{result_var.name}': stored payload predates the path-backed format; "
                "only the final time event's payload is recoverable from this result*"
            )
        dataset_list = getattr(self, "dataset_list", None)
        if not dataset_list or not 0 <= idx < len(dataset_list):
            logger.warning(
                "ResultDataSet '%s': cell %r indexes a dataset_list of length %d; the "
                "payload predates path-backed storage and its run's list is gone",
                result_var.name,
                val,
                len(dataset_list) if dataset_list else 0,
            )
            return pn.pane.Markdown(
                f"*'{result_var.name}': stored payload predates the path-backed format "
                "and is no longer recoverable from this result*"
            )
        ref = dataset_list[idx]
        if ref is None:
            return None
        # Renderer-supplied container wins, then the sample's, then the class's.
        resolved = container or self.declared_container(ref, result_var)
        return resolved(ref.obj) if resolved is not None else ref.obj

    def ds_to_container(  # pylint: disable=too-many-return-statements
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        container,
        legacy_trusted: bool = True,
        **kwargs,
    ) -> Any:
        """Render one sample of *result_var* out of *dataset*.

        ``legacy_trusted`` is threaded through to
        :meth:`_dataset_sample_to_container` for ``ResultDataSet`` cells; the
        over_time render path passes ``False`` for historical time indices whose
        legacy int cells cannot be resolved against the final run's
        ``dataset_list`` (see that method).

        Two kinds of container can apply, and they are different contracts:

        * the ``container`` argument, supplied by a renderer — a panel pane
          constructor, called with the value plus styling and layout keywords (this
          is what ``PaneResult.to_panes`` and ``video_container`` rely on);
        * a *declared* container, carried by the result variable or the stored
          sample — called with the object alone, so a single-argument renderer such
          as an ``xy_scatter`` spec works unchanged.

        A declared container beats the type's built-in ``to_container()``, which is
        what makes it possible to render a path as its contents rather than as a
        download widget.
        """
        if isinstance(result_var, (ResultDataSet, ResultReference)):
            # These two store a per-sample lookup key (a blob reference, or a legacy /
            # object index into a side list), so a value that is still an array
            # fails several frames from the cause. Name the dimension the caller
            # did not reduce instead.
            unreduced = self._unreduced_dims(dataset[result_var.name])
            if unreduced:
                raise ValueError(
                    f"cannot render one {type(result_var).__name__} sample for "
                    f"'{result_var.name}': dimension(s) {unreduced} were neither "
                    "selected nor reduced, so there is no single value to look up"
                )
        val = self.zero_dim_da_to_val(dataset[result_var.name])
        if isinstance(result_var, ResultDataSet):
            return self._dataset_sample_to_container(val, result_var, container, legacy_trusted)
        if isinstance(result_var, ResultReference):
            ref = self.object_index[val]
            if ref is not None:
                val = ref.obj
                # The sample's container, then the class's. Called with the object
                # alone, matching ResultDataSet, so one spec serves both.
                resolved = self.declared_container(ref, result_var)
                if resolved is not None:
                    return resolved(val)
        if container is not None:
            return container(val, styles={"background": "white"}, **kwargs)
        # A container declared on the result var beats the type's built-in default,
        # so a ResultPath can render its contents rather than a download widget.
        resolved = self.declared_container(result_var)
        if resolved is not None:
            return resolved(val)
        try:
            to_container = result_var.to_container()
            if to_container is not None:
                return to_container(val)
        except AttributeError as _:
            # TODO make sure all vars have to_container method
            pass
        return val

    @staticmethod
    def select_subsampling_divisions(
        dataset: xr.Dataset,
        subsampling_divisions: int,
        include_types: list[type] | None = None,
        exclude_names: list[str] | None = None,
    ) -> xr.Dataset:
        """Given a dataset, return a reduced dataset that only contains data from a specified subsampling_divisions.  By default all types of variables are filtered at the specified subsampling_divisions.  If you only want to get a reduced subsampling_divisions for some types of data you can pass in a list of types to get filtered, You can also pass a list of variables names to exclude from getting filtered
        Args:
            dataset (xr.Dataset): dataset to filter
            subsampling_divisions (int): desired data resolution subsampling_divisions
            include_types (list[type], optional): Only filter data of these types. Defaults to None.
            exclude_names (list[str], optional): Only filter data with these variable names. Defaults to None.

        Returns:
            xr.Dataset: A reduced dataset at the specified subsampling_divisions

        Example:  a dataset with float_var: [1,2,3,4,5] cat_var: [a,b,c,d,e]

        select_subsampling_divisions(ds,2) -> [1,5] [a,e]
        select_subsampling_divisions(ds,2,(float)) -> [1,5] [a,b,c,d,e]
        select_subsampling_divisions(ds,2,exclude_names=["cat_var]) -> [1,5] [a,b,c,d,e]

        see test_bench_result_base.py -> test_select_subsampling_divisions()
        """
        # Hoisted out of the loop: listify() only returns None for a None input, so
        # narrowing these once says what the old per-iteration
        # `x is not None and ... listify(x)` pair said, without re-testing the same
        # condition through a function whose None arm is unreachable by then.
        allowed_dtypes = listify(include_types)
        excluded_coords = listify(exclude_names)
        coords_no_repeat = {}
        for c, v in dataset.coords.items():
            if c != "repeat":
                vals = v.to_numpy()
                include = True
                if allowed_dtypes is not None and vals.dtype not in allowed_dtypes:
                    include = False
                if excluded_coords is not None and c in excluded_coords:
                    include = False
                if include:
                    coords_no_repeat[c] = with_subsampling_divisions(
                        v.to_numpy(), subsampling_divisions
                    )
        return dataset.sel(coords_no_repeat)

    @staticmethod
    def select_level(
        dataset: xr.Dataset,
        level: int,
        include_types: list[type] | None = None,
        exclude_names: list[str] | None = None,
    ) -> xr.Dataset:
        """Deprecated: use :meth:`select_subsampling_divisions` instead."""
        import warnings

        warnings.warn(
            "'select_level' is deprecated; use 'select_subsampling_divisions' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return BenchResultBase.select_subsampling_divisions(
            dataset,
            subsampling_divisions=level,
            include_types=include_types,
            exclude_names=exclude_names,
        )

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
