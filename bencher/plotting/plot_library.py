from __future__ import annotations

from bencher.plotting.plot_collection import PlotCollection
from bencher.plotting.plot_types import PlotTypes
from bencher.plotting.plots.catplot import Catplot
from bencher.plotting.plots.heatmap import Heatmap
from bencher.plotting.plots.lineplot import Lineplot
from bencher.plotting.plots.scatterplot import Scatter
from bencher.plotting.plots.tables import Tables
from bencher.plotting.plots.volume import VolumePlot
from bencher.plotting.plots.surface import SurfacePlot

from bencher.plotting.plots.hv_interactive import HvInteractive


class PlotLibrary:
    """This class is a collection of static factory methods that define sets of plots.  It provides a sensible default PlotCollection out of the box but also enables the creation of custom PlotCollections"""

    @staticmethod
    def setup_sources() -> PlotCollection:
        """Shared method that collects all the possible plot types.  This is used by all the other methods that select different subsections of the plots

        Returns:
            PlotCollection: A PlotCollection with sources of plots defined, but none selected
        """
        plt_col = PlotCollection()
        plt_col.add_plotter_source(Catplot())
        plt_col.add_plotter_source(Tables())
        plt_col.add_plotter_source(Heatmap())
        plt_col.add_plotter_source(Lineplot())
        plt_col.add_plotter_source(Scatter())
        plt_col.add_plotter_source(HvInteractive())
        plt_col.add_plotter_source(VolumePlot())
        plt_col.add_plotter_source(SurfacePlot())

        return plt_col

    @staticmethod
    def default() -> PlotCollection:
        """Default PlotCollection.  This set of plots should provide a reasonable set of plots that cover the most common data plotting use cases

        Returns:
            PlotCollection: sensible default for PlotCollection
        """
        plt_col = PlotLibrary.setup_sources()
        # plt_col.add(PlotTypes.scatter_hv)

        plt_col.add(PlotTypes.swarmplot)
        plt_col.add(PlotTypes.heatmap_2D)  # 2d image of a surface
        plt_col.add(PlotTypes.lineplot)
        plt_col.add(PlotTypes.lineplot_hv)
        # plt_col.add(PlotTypes.lineplot_hv_overlay)
        # plt_col.add(PlotTypes.lineplot_hv_layout)
        plt_col.add(PlotTypes.scatter_hv)
        plt_col.add(PlotTypes.bar_hv)
        plt_col.add(PlotTypes.volume_plotly)
        plt_col.add(PlotTypes.cone_plotly)
        # plt_col.add(PlotTypes.lineplot_hv_subplot)
        plt_col.add(PlotTypes.scatter2D_sns)
        plt_col.add(PlotTypes.surface_hv)
        # plt_col.add(PlotTypes.hv_interactive)

        return plt_col

    @staticmethod
    def tables() -> PlotCollection:
        """Display only table summaries of the data

        Returns:
            PlotCollection: Only table plots
        """
        plt_col = PlotLibrary.setup_sources()
        plt_col.add(PlotTypes.dataframe_multi_index)
        plt_col.add(PlotTypes.dataframe_mean)
        return plt_col

    @staticmethod
    def all() -> PlotCollection:
        """Display the data in every possible way. All plots are included

        Returns:
            PlotCollection: All possible plots
        """
        plt_col = PlotLibrary.setup_sources()
        for pt in PlotTypes:  # iterate through all plot enums
            plt_col.add(pt)
        return plt_col

    @staticmethod
    def none() -> PlotCollection:
        """Set up a plot collection with no active plots

        Returns:
            PlotCollection: No plots
        """
        return PlotLibrary.setup_sources()
