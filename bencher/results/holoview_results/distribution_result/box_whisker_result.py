from __future__ import annotations
from typing import Optional, Any
import panel as pn
import holoviews as hv
from param import Parameter
import xarray as xr

from bencher.results.holoview_results.distribution_result.distribution_result import (
    DistributionResult,
)


class BoxWhiskerResult(DistributionResult):
    """A class for creating box and whisker plots from benchmark results.

    Box and whisker plots are useful for visualizing the distribution of data,
    including the median, quartiles, and potential outliers. This class provides
    methods to generate these plots from benchmark data, particularly useful for
    comparing distributions across different categorical variables or between
    different repetitions of the same benchmark.

    Box plots show:
    - The median (middle line in the box)
    - The interquartile range (IQR) as a box (25th to 75th percentile)
    - Whiskers extending to the furthest data points within 1.5*IQR
    - Outliers as individual points beyond the whiskers
    """

    def to_plot(
        self, result_var: Optional[Parameter] = None, override: bool = True, **kwargs: Any
    ) -> Optional[pn.panel]:
        """Generates a box and whisker plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a box plot
        and then passes the filtered data to to_boxplot_ds for rendering.

        Args:
            result_var (Optional[Parameter]): The result variable to plot. If None, uses the default.
            override (bool): Whether to override filter restrictions. Defaults to True.
            **kwargs (Any): Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the box plot if data is appropriate,
            otherwise returns filter match results.
        """
        return self.to_distribution_plot(
            self.to_boxplot_ds,
            result_var=result_var,
            override=override,
            **kwargs,
        )

    def to_boxplot_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs: Any
    ) -> hv.BoxWhisker:
        """Creates a box and whisker plot from the provided dataset.

        Given a filtered dataset, this method generates a box and whisker visualization showing
        the distribution of values for a result variable, potentially grouped by a categorical variable.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs (Any): Additional keyword arguments for plot customization such as:
                      - box_fill_color: Color for the box
                      - whisker_color: Color for the whiskers
                      - outlier_color: Color for outlier points
                      - line_width: Width of lines in the plot

        Returns:
            hv.BoxWhisker: A HoloViews BoxWhisker plot of the benchmark data.
        """
        return self._plot_distribution(dataset, result_var, hv.BoxWhisker, **kwargs)
