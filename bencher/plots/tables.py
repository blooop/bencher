from bencher.plot_signature import PlotProvider, PlotFilter, VarRange, PlotInput
from bencher.bench_cfg import BenchCfg, PltCntCfg
from bencher.bench_vars import ParametrizedSweep

from typing import List
import panel as pn


class Tables:
    """A class to display the result data in tabular form"""
    match_all = PlotFilter(
        float_range=VarRange(None, None),
        cat_range=VarRange(None, None),
        vector_len=VarRange(None, None),
        result_vars=VarRange(None, None),
    )

    def dataframe_raw(self, pl_in: PlotInput) -> List[pn.panel]:
        if self.match_all.matches(pl_in.plt_cnt_cfg):
            df = pl_in.bench_cfg.get_dataframe()
            return [pn.pane.DataFrame(df, name=self.dataframe_raw.__name__)]
        return []

    def dataframe_mean(self, pl_in: PlotInput) -> List[pn.panel]:
        if self.match_all.matches(pl_in.plt_cnt_cfg):
            df = pl_in.bench_cfg.ds.mean("repeat").to_dataframe().reset_index()
            return [pn.pane.DataFrame(df, name=self.dataframe_mean.__name__)]
        return []

    def xarray(self, pl_in: PlotInput) -> List[pn.panel]:
        if self.match_all.matches(pl_in.plt_cnt_cfg):
            return [pn.panel(pl_in.bench_cfg.ds, name=self.xarray.__name__)]
        return []
