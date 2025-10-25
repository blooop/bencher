from __future__ import annotations
import param
from bencher.bench_cfg import BenchCfg
from bencher.variables.results import PANEL_TYPES

from bencher.variables.inputs import (
    IntSweep,
    FloatSweep,
    BoolSweep,
    EnumSweep,
    StringSweep,
    YamlSweep,
)
from bencher.variables.time import TimeSnapshot


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

    print_debug = param.Boolean(
        True,
        doc="Print debug information about why a filter matches this config or not",
    )

    @staticmethod
    def generate_plt_cnt_cfg(
        bench_cfg: BenchCfg,
    ) -> PltCntCfg:
        """Given a BenchCfg work out how many float and cat variables there are and store in a PltCntCfg class

        Args:
            bench_cfg (BenchCfg): See BenchCfg definition

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
            if isinstance(iv, (IntSweep, FloatSweep, TimeSnapshot)):
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
        return plt_cnt_cfg

    def __str__(self):
        return f"float_cnt: {self.float_cnt}\ncat_cnt: {self.cat_cnt} \npanel_cnt: {self.panel_cnt}\nvector_len: {self.vector_len}"
