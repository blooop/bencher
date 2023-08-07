from __future__ import annotations

import inspect
import logging
from typing import Callable, List

import panel as pn

from bencher.bench_cfg import BenchCfg, PltCntCfg
from bencher.plotting.plot_filter import PlotInput, PlotProvider
from bencher.variables.parametrised_sweep import ParametrizedSweep


class PlotCollection:
    """A set of plot providers with filters that determine if they are able to plot the type of data in the results.  The plot collection can be customised with user defined plots or ones already defined by bencher. You can also take predefine PlotCollections defined in PlotLibrary and add or remove specific plots that you want to override.  The add and remove function accept strings, or StrEnums (which are equivalent to strings)"""

    def __init__(self) -> None:
        """A PlotCollection has a dictionary of function_name:function_pointer which are all the available types of plot. The plotters variable contains an ordered dictionary of the active plotting functions"""
        self.plotter_providers = {}
        self.plotters = {}

    def add_plotter_source(self, plotter_class_instance: PlotProvider) -> None:
        """Given a class definition that contains several plotting methods, get a list of all the methods of the class and add them to the dictionary of available plotting functions

        Args:
            plotter_class_instance (PlotProvider): A class that contains plotting methods
        """

        if not inspect.isclass(plotter_class_instance):
            self.plotter_providers |= dict(
                inspect.getmembers(plotter_class_instance, predicate=inspect.ismethod)
            )
        else:
            raise ValueError(
                "You need to pass an instance of a class not the class type, Add () to the end of the class name"
            )

    def add(self, plot_name: str, plot_fn: Callable = None) -> PlotCollection:
        """Add a plotting method to the list of active plotting functions

        Args:
            plot_name (str): The name of the plot to add.  This can either be a string, or from the StrEnum PlotTypes (which is also a string)
            plot_fn (Callable): A user defined plotting function.  If no function is supplied, the name of the function is looked up from the list of plotter sources that have been added to the plot collection.

        Returns:
            PlotCollection: Returns a reference to this class so that you can call with a fluent api, e.g plot_coll.add("barplot").remove("swarmplot")
        """
        if plot_fn is None:
            if plot_name in self.plotter_providers:
                self.plotters[plot_name] = self.plotter_providers[plot_name]
            else:
                raise ValueError("This plot was not found in the list of available plots")
        else:
            self.plotters[plot_name] = plot_fn
        return self

    def add_list(self, plot_names: List[str]) -> PlotCollection:
        """Add a list of plotting methods to the list of active plotting functions

        Args:
            plot_name (List[str]): A list of names of the plot to add. The list can contain either strings, or StrEnum PlotTypes (which is also a string)

        Returns:
            PlotCollection: Returns a reference to this class so that you can call with a fluent api, e.g plot_coll.add_list(["barplot","boxplot"]).remove("swarmplot")
        """
        for p in plot_names:
            self.add(p)
        return self

    def remove(self, plot_name: str) -> PlotCollection:
        """Remove a plotting method from the list of active plotting functions

        Args:
            plot_name (str): The name of the plot to add.  This can either be a string, or from the StrEnum PlotTypes (which is also a string)

        Returns:
            PlotCollection: Returns a reference to this class so that you can call with a fluent api, e.g plot_coll.remove(swarmplot).add(barplot)
        """
        self.plotters.pop(plot_name)
        return self

    def gather_plots(
        self, bench_cfg: BenchCfg, rv: ParametrizedSweep, plt_cnt_cfg: PltCntCfg
    ) -> pn.pane.panel:
        """This method returns a single plot based on 1 result variable and a set of input variables.  It dedeuces the correct plot type by passing it to several configuration functions that operate on the number of inputs

        Args:
            bench_cfg (BenchCfg): A config of the input vars
            rv (ParametrizedSweep): a config of the result variable
            plt_cnt_cfg (PltCntCfg): A config of how many input types there are
        Raises:
            ValueError: If the plot does not inherit from a pn.viewable.Viewable type
        """

        tabs = pn.Accordion()
        # logging.info(self.plotters.values())
        for plt_fn in self.plotters.values():
            plots = plt_fn(PlotInput(bench_cfg, rv, plt_cnt_cfg))
            if plots is not None:
                if type(plots) != list:
                    plots = [plots]
                for plt_instance in plots:
                    if not isinstance(plt_instance, pn.viewable.Viewable):
                        raise ValueError(
                            "The plot must be a viewable type (pn.viewable.Viewable or pn.panel)"
                        )
                    logging.info(f"plotting: {plt_instance.name}")
                    tabs.append(plt_instance)
        if len(tabs) > 0:
            tabs.active = list(range(len(tabs)))  # set all plots as active
        return tabs
