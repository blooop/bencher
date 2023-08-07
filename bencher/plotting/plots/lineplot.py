from typing import Optional

import panel as pn
import seaborn as sns
import hvplot.xarray  # noqa pylint: disable=unused-import

from bencher.plotting.plot_filter import PlotFilter, PlotInput, VarRange
from bencher.plotting.plot_types import PlotTypes
from bencher.plotting.plots.catplot import Catplot
from bencher.plt_cfg import PltCfgBase
from bencher.plotting.plots.plot_base import PlotBase


class Lineplot(PlotBase):
    # shared plot filter for lineplots
    plot_filter = PlotFilter(
        float_range=VarRange(1, 1),
        cat_range=VarRange(0, 1),
        vector_len=VarRange(1, 1),
        result_vars=VarRange(1, 1),
    )

    def lineplot(self, pl_in: PlotInput) -> Optional[pn.panel]:
        """generate a line plot

        Args:
            pl_in (PlotInput): data to plot

        Returns:
            Optional[pn.panel]: a line plot of the data
        """
        if self.plot_filter.matches(pl_in.plt_cnt_cfg):
            df = pl_in.bench_cfg.ds[pl_in.rv.name].to_dataframe().reset_index()
            sns_cfg = PltCfgBase()

            x = pl_in.plt_cnt_cfg.float_vars[0]
            y = pl_in.rv
            if pl_in.plt_cnt_cfg.cat_cnt > 0:
                sns_cfg.hue = pl_in.plt_cnt_cfg.cat_vars[0].name

            sns_cfg.x = x.name
            sns_cfg.y = y.name

            sns_cfg.kind = "line"
            sns_cfg.xlabel = f"{x.name} [{x.units}]"
            sns_cfg.ylabel = f"{sns_cfg.y} [{pl_in.rv.units}]"
            sns_cfg.title = self.title(x, y)

            fg = sns.relplot(df, **sns_cfg.as_sns_args())

            # TODO try to set this during the initial plot rather than after
            for ax in fg.axes.flatten():
                for tick in ax.get_xticklabels():
                    tick.set_rotation(45)

            return Catplot.plot_postprocess(fg, sns_cfg, PlotTypes.lineplot)
        return None

    # def lineplot_hv(self, pl_in: PlotInput) -> Optional[pn.panel]:
    #     """generate a line plot

    #     Args:
    #         pl_in (PlotInput): data to plot

    #     Returns:
    #         Optional[pn.panel]: a line plot of the data
    #     """
    #     if self.plot_filter.matches(pl_in.plt_cnt_cfg):
    #         da = pl_in.bench_cfg.ds[pl_in.rv.name]

    #         x = pl_in.plt_cnt_cfg.float_vars[0]
    #         y = pl_in.rv
    #         title = self.title(x, y)

    #         col = None
    #         if pl_in.plt_cnt_cfg.cat_cnt > 0:
    #             col = pl_in.plt_cnt_cfg.cat_vars[0]

    #         da[col.name] = ["absolute", "negate"]

    #         kwargs = {"x": x.name, "y": y.name}

    #         print(kwargs)

    #         pt = hv.Overlay()

    #         # look into:
    #         # https://holoviews.org/user_guide/Dimensioned_Containers.html

    #         df = da.to_dataframe()
    #         df = df.pivot_table(columns=[col.name], index=[x.name], values=[y.name])[y.name]
    #         print(df)
    #         # dag = da.groupby(col.name)[y.name]
    #         # dag = da.groupby(col.name)
    #         pt = df.hvplot.line()
    #         # pt *= dag.hvplot.line()
    #         # pt *= df.hvplot.line(y=col.values(False))
    #         # pt *= da.hvplot.line(groupby=col.name, **kwargs)
    #         # pt.opts(shared_axes=False, title=title)
    #         pt.opts(title=title)

    #         # mean = da.mean("repeat", keepdims=True, keep_attrs=True)
    #         return pn.Column(pt, name=PlotTypes.lineplot_hv)
    #     return None

    # def lineplot_hv_repeats(self, pl_in: PlotInput) -> Optional[pn.panel]:
    #     """generate a line plot

    #     Args:
    #         pl_in (PlotInput): data to plot

    #     Returns:
    #         Optional[pn.panel]: a line plot of the data
    #     """
    #     if self.plot_filter.matches(pl_in.plt_cnt_cfg):
    #         da = pl_in.bench_cfg.ds[pl_in.rv.name]

    #         x = pl_in.plt_cnt_cfg.float_vars[0]
    #         y = pl_in.rv
    #         title = self.title(x, y)

    #         col = None
    #         if pl_in.plt_cnt_cfg.cat_cnt > 0:
    #             col = pl_in.plt_cnt_cfg.cat_vars[0].name

    #         pt = hv.Overlay()
    #         hvds = hv.Dataset(da)
    #         import numpy as np

    #         # to read
    #         # https://medium.com/@shouke.wei/data-visualization-with-hvplot-iii-interactive-multiple-plots-e73124742df4

    #         # pt *= hvds.to(hv.Curve, x.name, "repeat")
    #         # pt *= hv.Curve(hvds, kdims=[x.name], vdims=[y.name])
    #         # pt *= hv.Spread(hvds.aggregate(y.name, np.mean, np.std), kdims=[y.name])
    #         # return None
    #         print(hvds)

    #         pt += hvds

    #         pt *= hv.Spread(
    #             hvds.aggregate("repeat", np.mean, np.std), kdims=[x.name], vdims=[y.name]
    #         )
    #         pt *= hv.Curve(hvds.aggregate("repeat", np.mean), kdims=[x.name], vdims=[y.name])

    #         col = pn.Column(name="spread")

    #         col.append(pt)

    #         return col
    #         # return da.to(hv.Spread)

    #         stats, std = self.calculate_stats(da)

    #         kwargs = {"x": x.name, "y": "mean"}

    #         std_kwargs = kwargs | {"y": "std_low", "y2": "std_high"}

    #         pt *= stats.hvplot.area(**std_kwargs).opts(alpha=0.2)
    #         # pt *= hv.Spread(std).opts(alpha=0.2)
    #         pt *= stats.hvplot.line(**kwargs)

    #         pt.opts(title=title)

    #         return pn.Column(pt, name=PlotTypes.lineplot_hv_repeats)
    #     return None

    # def lineplot_hv_subplot(self, pl_in: PlotInput) -> Optional[pn.panel]:
    #     """generate a line plot

    #     Args:
    #         pl_in (PlotInput): data to plot

    #     Returns:
    #         Optional[pn.panel]: a line plot of the data
    #     """
    #     if PlotFilter(
    #         float_range=VarRange(1, 1),
    #         cat_range=VarRange(1, 1),
    #         vector_len=VarRange(1, 1),
    #         result_vars=VarRange(1, 1),
    #     ).matches(pl_in.plt_cnt_cfg):
    #         da = pl_in.bench_cfg.ds[pl_in.rv.name]
    #         da = da.mean("repeat")

    #         lines = pl_in.plt_cnt_cfg.cat_vars[0].values(False)
    #         print(lines)
    #         return pn.Column(
    #             da.hvplot.line(subplots=True),
    #             name=PlotTypes.lineplot_hv_subplot,
    #         )
    #     return None
