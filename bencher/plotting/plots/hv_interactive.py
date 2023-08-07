from typing import Optional
import panel as pn
import hvplot.xarray  # noqa pylint: disable=unused-import
import holoviews as hv  # noqa pylint: disable=unused-import

from bencher.plotting.plot_filter import PlotFilter, PlotInput, VarRange
from bencher.plotting.plot_types import PlotTypes  # noqa pylint: disable=unused-import
from bencher.plotting.plots.plot_base import PlotBase


class HvInteractive(PlotBase):
    float_0_cat_at_least1_vec_1_res_1 = PlotFilter(
        float_range=VarRange(0, 0),
        cat_range=VarRange(1, None),
        vector_len=VarRange(1, 1),
        result_vars=VarRange(1, 1),
    )

    # shared plot filter for catplots
    scatter_filter = PlotFilter(
        float_range=VarRange(0, 0),
        cat_range=VarRange(1, None),
        vector_len=VarRange(1, 1),
        result_vars=VarRange(1, 1),
    )

    lineplot_filter = PlotFilter(
        float_range=VarRange(1, None),
        cat_range=VarRange(0, 0),
        vector_len=VarRange(1, 1),
        result_vars=VarRange(1, 1),
    )

    lineplot_multi_filter = PlotFilter(
        float_range=VarRange(2, None),
        cat_range=VarRange(0, 0),
        vector_len=VarRange(1, 1),
        result_vars=VarRange(-1, -1),
    )

    def bar_hv(self, pl_in: PlotInput) -> Optional[pn.panel]:
        if self.scatter_filter.matches(pl_in.plt_cnt_cfg):
            pt = pl_in.bench_cfg.to_bar()
            return pn.Column(pt, name=PlotTypes.bar_hv)

        return None

    def scatter_hv(self, pl_in: PlotInput) -> Optional[pn.panel]:
        if self.scatter_filter.matches(pl_in.plt_cnt_cfg):
            # pt = pl_in.bench_cfg.to_bar()
            pt = pl_in.bench_cfg.to_scatter()
            # pt *= pl_in.bench_cfg.get_hv_dataset(False).to(hv.Scatter).opts(color="k", jitter=0.5)

            return pn.Column(pt, name=PlotTypes.scatter_hv)

        return None

        # return None
        # if self.scatter_filter.matches(pl_in.plt_cnt_cfg):
        #     x = pl_in.plt_cnt_cfg.cat_vars[0]
        #     y = pl_in.rv
        #     ds = pl_in.bench_cfg.ds[pl_in.rv.name]
        #     title = f"{x.name} vs {y.name}"

        #     if pl_in.plt_cnt_cfg.cat_cnt > 1:
        #         c = pl_in.plt_cnt_cfg.cat_vars[1].name
        #         ds = ds.set_index(c)

        #     pt = hv.Overlay()

        #     pt *= ds.mean("repeat").hvplot(x=x.name, y=y.name, kind="bar")
        #     for r in ds.coords["repeat"]:
        #         pt *= ds.sel(repeat=r).hvplot(
        #             x=x.name, y=y.name, kind="scatter", rot=45, color="black"
        #         )
        #     # pt = pl_in.bench_cfg.to_points()

        #     return pn.Column(pt.opts(height=600, title=title), name=PlotTypes.scatter_hv)

        # return None

    def lineplot_hv(self, pl_in: PlotInput) -> Optional[pn.panel]:
        if self.lineplot_filter.matches(pl_in.plt_cnt_cfg):
            tit = self.title(pl_in.bench_cfg.input_vars[0], pl_in.rv)
            return pn.Column(
                pl_in.bench_cfg.to_curve().opts(title=tit, width=600, height=600),
                name=PlotTypes.lineplot_hv,
            )
        return None

    def lineplot_hv_overlay(self, pl_in: PlotInput) -> Optional[pn.panel]:
        if False & self.lineplot_multi_filter.matches(pl_in.plt_cnt_cfg):
            return pn.Column(
                pl_in.bench_cfg.to_curve().overlay(pl_in.bench_cfg.input_vars[-1].name),
                name=PlotTypes.lineplot_hv_overlay,
            )
        return None

    def lineplot_hv_layout(self, pl_in: PlotInput) -> Optional[pn.panel]:
        if False & self.lineplot_multi_filter.matches(pl_in.plt_cnt_cfg):
            return pn.Column(
                pl_in.bench_cfg.to_curve().layout(),
                name=PlotTypes.lineplot_hv_layout,
            )
        return None
