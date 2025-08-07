from __future__ import annotations
from typing import Optional
import panel as pn
from param import Parameter
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class BarResult(HoloviewResult):
    """A class for creating bar chart visualizations from benchmark results.

    Bar charts are effective for comparing values across categorical variables or
    discrete data points. This class provides methods to generate bar charts that
    display benchmark results, particularly useful for comparing performance metrics
    between different configurations or categories.
    """

    def to_plot(
        self, result_var: Parameter = None, override: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        return self.to_bar(result_var, override, **kwargs)

    def to_bar(
        self,
        result_var: Parameter = None,
        override: bool = True,
        target_dimension: int = 2,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a bar chart from benchmark data.

        This method applies filters to ensure the data is appropriate for a bar chart
        and then passes the filtered data to to_bar_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 2.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the bar chart if data is appropriate,
                              otherwise returns filter match results.
        """
        common = {
            "float_range": VarRange(0, 0),
            "cat_range": VarRange(0, None),
            "panel_range": VarRange(0, None),
            "target_dimension": target_dimension,
            "result_var": result_var,
            "override": override,
            **kwargs,
        }

        scenarios = [
            {
                "repeats_range": VarRange(1, 1),
                "reduce": ReduceType.SQUEEZE,
                "result_types": (ResultVar,),
            },
            {
                "repeats_range": VarRange(2, None),
                "reduce": ReduceType.REDUCE,
                "result_types": (ResultBool,),
            },
        ]

        for params in scenarios:
            res = self.filter(self.to_bar_ds, **common, **params)
            if res is not None:
                return res
        return None

    def to_bar_ds(self, dataset: xr.Dataset, result_var: Parameter = None, **kwargs):
        """Creates a bar chart from the provided dataset.

        Given a filtered dataset, this method generates a bar chart visualization showing
        values of the result variable, potentially grouped by categorical variables.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            **kwargs: Additional keyword arguments passed to the bar chart options.

        Returns:
            hvplot.element.Bars: A bar chart visualization of the benchmark data.
        """
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 2:
            by = self.plt_cnt_cfg.cat_vars[1].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        time_widget_args = self.time_widget(title)
        return da_plot.hvplot.bar(by=by, **time_widget_args, **kwargs).opts(
            title=title,
            ylabel=f"{result_var.name} [{result_var.units}]",
            xrotation=30,  # Rotate x-axis labels by 30 degrees
            **kwargs,
        )
