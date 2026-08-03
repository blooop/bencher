from __future__ import annotations

from collections.abc import Callable
from typing import Any

import holoviews as hv
import panel as pn
import xarray as xr
from param import Parameter

from bencher.plotting.plot_filter import VarRange
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult, PlotResult
from bencher.utils import params_to_str
from bencher.variables.results import ResultFloat


class DistributionResult(HoloviewResult):
    """A base class for creating distribution plots (violin, box-whisker) from benchmark results.

    This class provides common functionality for various distribution plot types that show
    the distribution shape of the data. Child classes implement specific plot types
    (e.g., violin plots, box and whisker plots) but share filtering and data preparation logic.

    Distribution plots are particularly useful for visualizing the statistical spread of
    benchmark metrics across different configurations, allowing for better understanding
    of performance variability.
    """

    def to_distribution_plot(
        self,
        plot_method: Callable[[xr.Dataset, Parameter, Any], hv.Element],
        result_var: Parameter | None = None,
        override: bool = True,
        **kwargs: Any,
    ) -> pn.panel | None:
        """Generates a distribution plot from benchmark data.

        This method applies filters to ensure the data is appropriate for distribution plots
        and then passes the filtered data to the specified plot method for rendering.

        Args:
            plot_method: The method to use for creating the specific plot type (e.g., violin, box-whisker)
            result_var: The result variable to plot. If None, uses the default.
            override: Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            A panel containing the plot if data is appropriate,
            otherwise returns filter match results.
        """
        return self.filter(
            plot_method,
            float_range=VarRange.exactly(0),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.at_least(2),
            reduce=ReduceType.NONE,
            target_dimension=self.plt_cnt_cfg.cat_cnt + 1,  # +1 cos we have a repeats dimension
            result_var=result_var,
            result_types=(ResultFloat,),
            override=override,
            **kwargs,
        )

    @staticmethod
    def _build_distribution_overlay(df, plot_classes, kdims, var_name, result_var, title, **kwargs):
        """Build an hv.Overlay from one or more distribution plot classes."""
        overlay = hv.Overlay()
        for plot_cls in plot_classes:
            overlay *= plot_cls(
                df,
                kdims=kdims,
                vdims=[var_name],
            ).opts(
                title=title,
                ylabel=f"{var_name} [{result_var.units}]",
                xrotation=30,
                **kwargs,
            )
        return overlay

    def _plot_distribution(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        plot_class: type[hv.Selection1DExpr],
        **kwargs: Any,
    ) -> PlotResult:
        """Prepares data for distribution plots and creates the plot.

        This method handles common operations needed for all distribution plot types,
        including converting data formats, setting up dimensions, and configuring
        plot aesthetics.

        Args:
            dataset: The dataset containing benchmark results.
            result_var: The result variable to plot.
            plot_class: The HoloViews plot class to use (e.g., hv.Violin, hv.BoxWhisker)
            **kwargs: Additional keyword arguments for plot customization.

        Returns:
            An ``hv.Overlay`` of the requested plot class(es); for an over_time
            dataset, whatever ``_build_time_holomap_raw`` wraps it in (see
            ``PlotResult``) -- a ``pn.Column`` in practice.

        The return type is **not** ``plot_class``, and is not even an ``hv.Element``:
        ``_build_distribution_overlay`` composes into an ``hv.Overlay`` unconditionally
        (it accepts a *list* of plot classes), and ``Overlay`` is not an ``hv.Element``
        subclass -- it descends from ``Dimensioned`` by a different route. Callers
        wanting the bare element must index into the overlay.
        """
        var_name = result_var.name
        title = self.title_from_ds(dataset[var_name], result_var, **kwargs)
        kdims = params_to_str(self.plt_cnt_cfg.cat_vars)

        if not isinstance(plot_class, list):
            plot_class = [plot_class]

        use_holomap = self._use_holomap_for_time(dataset)

        if use_holomap:
            da = dataset[var_name]

            def make_dist(da_window):
                df = da_window.to_dataframe().reset_index()
                return self._build_distribution_overlay(
                    df, plot_class, kdims, var_name, result_var, title, **kwargs
                )

            return self._build_time_holomap_raw(da, make_dist)

        df = dataset[var_name].to_dataframe().reset_index()
        return self._build_distribution_overlay(
            df, plot_class, kdims, var_name, result_var, title, **kwargs
        )
