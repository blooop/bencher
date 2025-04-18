from __future__ import annotations
from typing import Optional
import panel as pn
import holoviews as hv
from param import Parameter
import xarray as xr

import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
from bencher.results.bench_result_base import ReduceType

from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar


from bencher.results.holoview_results.holoview_result import HoloviewResult


class BoxWhiskerResult(HoloviewResult):
    """A class for creating box and whisker plots from benchmark results.

    Box and whisker plots are useful for visualizing the distribution of data,
    including the median, quartiles, and potential outliers. This class provides
    methods to generate these plots from benchmark data, particularly useful for
    comparing distributions across different categorical variables or between
    different repetitions of the same benchmark.
    """

    def to_boxplot(
        self, result_var: Parameter = None, override: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        """Generates a box and whisker plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a box plot
        and then passes the filtered data to to_boxplot_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the box plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.filter(
            self.to_boxplot_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.NONE,
            target_dimension=2,
            result_var=result_var,
            result_types=(ResultVar),
            override=override,
            **kwargs,
        )

    def to_boxplot_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs) -> hv.BoxWhisker:
        """Creates a box and whisker plot from the provided dataset.

        Given a filtered dataset, this method generates a box and whisker visualization showing
        the distribution of values for a result variable, potentially grouped by a categorical variable.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the box plot options.

        Returns:
            hv.BoxWhisker: A HoloViews BoxWhisker plot of the benchmark data.
        """
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 2:
            by = self.plt_cnt_cfg.cat_vars[1].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        time_widget_args = self.time_widget(title)
        # return da_plot.hvplot.box(by=by, **time_widget_args, **kwargs)
        # return da_plot.hvplot.box( **time_widget_args, **kwargs)
        print(kwargs)
        return da_plot.hvplot.box(y=result_var.name, by=by, **time_widget_args, **kwargs)
