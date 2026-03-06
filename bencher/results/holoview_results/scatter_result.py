from __future__ import annotations
from typing import Optional
import panel as pn
from param import Parameter

import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar
from bencher.results.holoview_results.holoview_result import HoloviewResult


class ScatterResult(HoloviewResult):
    """A class for creating scatter plots from benchmark results.

    Scatter plots are useful for visualizing the distribution of individual data points
    and identifying patterns, clusters, or outliers. This class generates scatter plots
    that can be grouped by categorical variables.
    """

    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        """Creates a scatter plot. See ``to_scatter`` for parameters."""
        return self.to_scatter(**kwargs)

    def to_scatter(
        self, result_var: Parameter | None = None, override: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        """Creates a standard scatter plot from benchmark data.

        Args:
            result_var (Parameter, optional): The result variable to plot.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the scatter plot options.

        Returns:
            Optional[pn.panel]: A panel containing the scatter plot, or filter match results.
        """
        return self.filter(
            self._to_scatter_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            reduce=ReduceType.SQUEEZE,
            result_var=result_var,
            result_types=(ResultVar,),
            override=override,
            **kwargs,
        )

    def _to_scatter_ds(  # pylint: disable=unused-argument
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> Optional[pn.panel]:
        """Creates a scatter plot from the provided dataset.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the scatter plot.

        Returns:
            Optional[pn.panel]: A scatter plot visualization.
        """
        by = None
        if self.plt_cnt_cfg.cat_cnt > 1:
            by = [v.name for v in self.bench_cfg.input_vars[1:]]
        return dataset.hvplot.scatter(by=by, subplots=False, **kwargs).opts(
            title=self.to_plot_title()
        )
