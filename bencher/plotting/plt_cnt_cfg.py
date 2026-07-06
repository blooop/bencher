from __future__ import annotations

from typing import Optional

import param
import xarray as xr

from bencher.bench_cfg import BenchCfg
from bencher.variables.results import (
    PANEL_TYPES,
    ResultBool,
    ResultContainer,
    ResultDataSet,
    ResultFloat,
    ResultHmap,
    ResultImage,
    ResultPath,
    ResultReference,
    ResultString,
    ResultVec,
    ResultVideo,
    ResultVolume,
)

from bencher.variables.inputs import (
    IntSweep,
    FloatSweep,
    BoolSweep,
    EnumSweep,
    StringSweep,
    YamlSweep,
)
from bencher.variables.time import TimeSnapshot, TimeEvent

# Most-derived first: kind classification takes the first isinstance match
# (ResultBool subclasses ResultFloat; ResultRerun subclasses ResultContainer).
_RESULT_KIND_ORDER = (
    (ResultBool, "bool"),
    (ResultFloat, "float"),
    (ResultVec, "vec"),
    (ResultImage, "image"),
    (ResultVideo, "video"),
    (ResultPath, "path"),
    (ResultString, "string"),
    (ResultDataSet, "dataset"),
    (ResultContainer, "container"),
    (ResultHmap, "hmap"),
    (ResultReference, "reference"),
    (ResultVolume, "volume"),
)


def result_kind(result_var) -> str:
    """Classify a result variable into a coarse, serializable kind name used by
    plot-selection signatures (A2)."""
    for cls, kind in _RESULT_KIND_ORDER:
        if isinstance(result_var, cls):
            return kind
    return "unknown"


class PltCntCfg(param.Parameterized):
    """Plot Count Config"""

    float_vars = param.List(doc="A list of float vars in order of plotting, x then y")
    float_cnt = param.Integer(0, doc="The number of float variables to plot")
    cat_vars = param.List(doc="A list of categorical values to plot in order hue,row,col")
    cat_cnt = param.Integer(0, doc="The number of cat variables")
    vector_len = param.Integer(1, doc="The vector length of the return variable , scalars = len 1")
    result_vars = param.Integer(1, doc="The number result variables to plot")  # todo remove
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
        doc="Repeat samples actually present in the data (min non-NaN count over the repeat "
        "dim), as opposed to the configured `repeats`; 0 when no dataset was provided",
    )

    print_debug = param.Boolean(
        True,
        doc="Print debug information about why a filter matches this config or not",
    )

    @staticmethod
    def generate_plt_cnt_cfg(
        bench_cfg: BenchCfg,
        ds: Optional[xr.Dataset] = None,
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
            if isinstance(iv, (IntSweep, FloatSweep, TimeSnapshot, TimeEvent)):
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
        plt_cnt_cfg.repeats = bench_cfg.repeats
        plt_cnt_cfg.inputs_cnt = len(bench_cfg.input_vars)

        plt_cnt_cfg.has_time = bool(bench_cfg.over_time) or any(
            isinstance(iv, (TimeSnapshot, TimeEvent)) for iv in bench_cfg.input_vars
        )
        plt_cnt_cfg.result_kinds = {rv.name: result_kind(rv) for rv in bench_cfg.result_vars}
        plt_cnt_cfg.cat_levels = {v.name: len(v.values()) for v in plt_cnt_cfg.cat_vars}
        if ds is not None:
            if "over_time" in ds.dims:
                plt_cnt_cfg.time_steps = int(ds.sizes["over_time"])
            plt_cnt_cfg.samples_per_point = _samples_per_point(ds)
        return plt_cnt_cfg

    def __str__(self):
        return f"float_cnt: {self.float_cnt}\ncat_cnt: {self.cat_cnt} \npanel_cnt: {self.panel_cnt}\nvector_len: {self.vector_len}"


def _samples_per_point(ds: xr.Dataset) -> int:
    """The number of repeat samples actually present at the sparsest sweep point:
    the minimum non-NaN count along the repeat dimension over all result variables
    that carry it. Differs from the configured `repeats` when runs are missing
    (missing values are stored as NaN)."""
    if "repeat" not in ds.dims:
        return 1 if len(ds.data_vars) else 0
    counts = [
        int(da.notnull().sum(dim="repeat").min())
        for da in ds.data_vars.values()
        if "repeat" in da.dims
    ]
    return min(counts) if counts else 0
