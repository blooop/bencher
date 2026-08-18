from __future__ import annotations

import math

import param
import xarray as xr

from bencher.bench_cfg import BenchCfg
from bencher.variables.inputs import (
    BoolSweep,
    EnumSweep,
    FloatSweep,
    IntSweep,
    StringSweep,
    YamlSweep,
)
from bencher.variables.results import (
    PANEL_TYPES,
    result_kind,
    result_missing_fill,
)
from bencher.variables.time import TimeEvent, TimeSnapshot

__all__ = ["PltCntCfg", "result_kind"]

# Time-like sweep inputs: drives both their classification as float axes and
# has_time, so the two facts can't drift apart.
TIME_TYPES = (TimeSnapshot, TimeEvent)


class PltCntCfg(param.Parameterized):
    """Plot Count Config"""

    float_vars = param.List(doc="A list of float vars in order of plotting, x then y")
    float_cnt = param.Integer(0, doc="The number of float variables to plot")
    cat_vars = param.List(doc="A list of categorical values to plot in order hue,row,col")
    cat_cnt = param.Integer(0, doc="The number of cat variables")
    panel_vars = param.List(doc="A list of panel results")
    panel_cnt = param.Integer(0, doc="Number of results represent as panel panes")
    repeats = param.Integer(0, doc="The number of repeat samples")
    inputs_cnt = param.Integer(0, doc="The number of repeat samples")

    # Richer signature facts (A2 Phase S1) — additive alongside the counts above.
    has_time = param.Boolean(
        False, doc="True when the sweep has a temporal axis (over_time or a time input var)"
    )
    time_steps = param.Integer(
        0, doc="Number of time points present in the dataset's over_time axis (0 = no axis)"
    )
    result_kinds = param.Dict(
        default={}, doc="result variable name -> coarse kind (float, bool, vec, image, video, ...)"
    )
    cat_levels = param.Dict(
        default={}, doc="categorical input variable name -> number of levels swept"
    )
    samples_per_point = param.Integer(
        0,
        doc="Repeat samples actually present in the data (min non-missing count over the "
        "repeat dim at the latest time step), as opposed to the configured `repeats`; "
        "0 when no dataset was provided",
    )

    print_debug = param.Boolean(
        True,
        doc="Print debug information about why a filter matches this config or not",
    )

    @staticmethod
    def generate_plt_cnt_cfg(
        bench_cfg: BenchCfg,
        ds: xr.Dataset | None = None,
    ) -> PltCntCfg:
        """Given a BenchCfg work out how many float and cat variables there are and store in a PltCntCfg class

        Args:
            bench_cfg (BenchCfg): See BenchCfg definition
            ds (xr.Dataset, optional): The collected result dataset. When provided, the
                data-derived signature facts (time_steps, samples_per_point) are
                computed from it; without it they stay at their defaults.

        Raises:
            ValueError: If no plotting procedure could be automatically detected

        Returns:
            PltCntCfg: see PltCntCfg definition
        """
        plt_cnt_cfg = PltCntCfg()
        # plt_cnt_cfg.float_vars = deepcopy(bench_cfg.iv_time)

        plt_cnt_cfg.cat_vars = []
        plt_cnt_cfg.float_vars = []

        for iv in bench_cfg.input_vars:
            type_allocated = False
            if isinstance(iv, (IntSweep, FloatSweep, *TIME_TYPES)):
                # if "IntSweep" in typestr or "FloatSweep" in typestr:
                plt_cnt_cfg.float_vars.append(iv)
                type_allocated = True
            if isinstance(iv, (EnumSweep, BoolSweep, StringSweep, YamlSweep)):
                # if "EnumSweep" in typestr or "BoolSweep" in typestr or "StringSweep" in typestr:
                plt_cnt_cfg.cat_vars.append(iv)
                type_allocated = True

            if not type_allocated:
                raise ValueError(f"No rule for type {type(iv)}")

        for rv in bench_cfg.result_vars:
            if isinstance(rv, PANEL_TYPES):
                plt_cnt_cfg.panel_vars.append(rv)

        plt_cnt_cfg.float_cnt = len(plt_cnt_cfg.float_vars)
        plt_cnt_cfg.cat_cnt = len(plt_cnt_cfg.cat_vars)
        plt_cnt_cfg.panel_cnt = len(plt_cnt_cfg.panel_vars)
        plt_cnt_cfg.repeats = bench_cfg.execution.repeats
        plt_cnt_cfg.inputs_cnt = len(bench_cfg.input_vars)

        plt_cnt_cfg.has_time = bool(bench_cfg.time.over_time) or any(
            isinstance(iv, TIME_TYPES) for iv in bench_cfg.input_vars
        )
        plt_cnt_cfg.result_kinds = {rv.name: result_kind(rv) for rv in bench_cfg.result_vars}
        plt_cnt_cfg.cat_levels = {v.name: len(v.values()) for v in plt_cnt_cfg.cat_vars}
        if ds is not None:
            if "over_time" in ds.dims:
                plt_cnt_cfg.time_steps = int(ds.sizes["over_time"])
            plt_cnt_cfg.samples_per_point = _samples_per_point(ds, bench_cfg.result_vars)
        return plt_cnt_cfg

    def __str__(self):
        return (
            f"float_cnt: {self.float_cnt}\n"
            f"cat_cnt: {self.cat_cnt}\n"
            f"panel_cnt: {self.panel_cnt}\n"
            f"has_time: {self.has_time}\n"
            f"time_steps: {self.time_steps}\n"
            f"result_kinds: {self.result_kinds}\n"
            f"cat_levels: {self.cat_levels}\n"
            f"samples_per_point: {self.samples_per_point}"
        )


def _missing_mask(da: xr.DataArray, rv) -> xr.DataArray:
    """True where an entry holds *rv*'s missing-value sentinel (see
    ``result_missing_fill``); plain NaN when the variable is unknown."""
    if rv is not None:
        fill, _ = result_missing_fill(rv)
        if not (isinstance(fill, float) and math.isnan(fill)):
            return da == fill
    return da.isnull()


def _samples_per_point(ds: xr.Dataset, result_vars=None) -> int:
    """The number of repeat samples actually present at the sparsest sweep point:
    the minimum non-missing count along the repeat dimension over the result
    variables that carry it. Differs from the configured `repeats` when runs are
    missing. Missingness is each variable's storage sentinel (NaN / -1 / "NAN",
    matched to `result_vars` by name) so object- and reference-backed misses
    count too. Only the latest `over_time` step is inspected — older steps carry
    structural padding when repeats or levels grew between runs. Variables
    without the repeat dimension are ignored when another variable carries it
    (a lone panel var must not mask real repeats); if none carries it, each
    point holds one sample, or none at all for a dataset with no result data."""
    rv_by_name = {rv.name: rv for rv in result_vars} if result_vars else {}
    counts = []
    for name, da in ds.data_vars.items():
        if "repeat" not in da.dims:
            continue
        if "over_time" in da.dims:
            if da.sizes["over_time"] == 0:
                counts.append(0)
                continue
            da = da.isel(over_time=-1)
        per_point = (~_missing_mask(da, rv_by_name.get(name))).sum(dim="repeat")
        counts.append(int(per_point.min()) if per_point.size else 0)
    if counts:
        return min(counts)
    return 1 if len(ds.data_vars) else 0
