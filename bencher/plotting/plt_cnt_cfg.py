from __future__ import annotations

import math
from typing import TYPE_CHECKING

import param

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

if TYPE_CHECKING:
    from collections.abc import Sequence

    import xarray as xr

    from bencher.bench_cfg import BenchCfg

__all__ = ["PltCntCfg", "result_kind"]

# Time-like sweep inputs: drives both their classification as float axes and
# has_time, so the two facts can't drift apart.
TIME_TYPES = (TimeSnapshot, TimeEvent)


class PltCntCfg(param.Parameterized):
    """Plot Count Config."""

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
        """Count the float and categorical variables in a BenchCfg and store them in a PltCntCfg.

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

        plt_cnt_cfg.cat_vars = []
        plt_cnt_cfg.float_vars = []

        for iv in bench_cfg.input_vars:
            type_allocated = False
            if isinstance(iv, (IntSweep, FloatSweep, *TIME_TYPES)):
                plt_cnt_cfg.float_vars.append(iv)
                type_allocated = True
            if isinstance(iv, (EnumSweep, BoolSweep, StringSweep, YamlSweep)):
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
        plt_cnt_cfg.repeats = bench_cfg.repeats
        plt_cnt_cfg.inputs_cnt = len(bench_cfg.input_vars)

        plt_cnt_cfg.has_time = bool(bench_cfg.over_time) or any(
            isinstance(iv, TIME_TYPES) for iv in bench_cfg.input_vars
        )
        plt_cnt_cfg.result_kinds = {rv.name: result_kind(rv) for rv in bench_cfg.result_vars}
        plt_cnt_cfg.cat_levels = {v.name: len(v.values()) for v in plt_cnt_cfg.cat_vars}
        if ds is not None:
            if "over_time" in ds.dims:
                plt_cnt_cfg.time_steps = int(ds.sizes["over_time"])
            plt_cnt_cfg.samples_per_point = _samples_per_point(ds, bench_cfg.result_vars)
        return plt_cnt_cfg

    def __str__(self) -> str:
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


def _missing_mask(da: xr.DataArray, rv: param.Parameter | None) -> xr.DataArray:
    """Mark the entries that hold *rv*'s missing-value sentinel.

    The sentinel comes from ``result_missing_fill``; plain NaN is used when the
    variable is unknown.
    """
    if rv is not None:
        fill, _ = result_missing_fill(rv)
        if not (isinstance(fill, float) and math.isnan(fill)):
            return da == fill
    return da.isnull()


def _samples_per_point(ds: xr.Dataset, result_vars: Sequence[param.Parameter] | None = None) -> int:
    """Count the repeat samples actually present at the sparsest sweep point.

    This is the minimum non-missing count along the repeat dimension over the result
    variables that carry it. Differs from the configured `repeats` when runs are
    missing. Missingness is each variable's storage sentinel (NaN / -1 / "NAN",
    matched to `result_vars` by name) so object- and reference-backed misses
    count too. Only the latest `over_time` step is inspected — older steps carry
    structural padding when repeats or levels grew between runs. Variables
    without the repeat dimension are ignored when another variable carries it
    (a lone panel var must not mask real repeats); if none carries it, each
    point holds one sample, or none at all for a dataset with no result data.
    """
    rv_by_name = {rv.name: rv for rv in result_vars} if result_vars else {}
    counts = []
    for name, da in ds.data_vars.items():
        if "repeat" not in da.dims:
            continue
        if "over_time" in da.dims:
            if da.sizes["over_time"] == 0:
                counts.append(0)
                continue
            latest = da.isel(over_time=-1)
        else:
            latest = da
        per_point = (~_missing_mask(latest, rv_by_name.get(name))).sum(dim="repeat")
        counts.append(int(per_point.min()) if per_point.size else 0)
    if counts:
        return min(counts)
    return 1 if len(ds.data_vars) else 0
