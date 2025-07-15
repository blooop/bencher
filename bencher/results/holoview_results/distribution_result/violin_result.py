from __future__ import annotations
from typing import Optional, Any
import panel as pn
import holoviews as hv
from param import Parameter
import xarray as xr

from bencher.results.holoview_results.distribution_result.distribution_result import (
    DistributionResult,
)


class ViolinResult(DistributionResult):
    """A class for creating violin plots from benchmark results.

    Violin plots combine aspects of box plots with kernel density plots, showing
    the distribution shape of the data. This class provides methods to generate
    these plots from benchmark data, which is particularly useful for visualizing
    the distribution of metrics across different configurations or repetitions.

    Violin plots display:
    - The full probability density of the data (the width of the "violin" at each point)
    - Summary statistics like median and interquartile ranges
    - The overall distribution shape, revealing features like multi-modality that
      box plots might miss
    """

    def to_plot(
        self, result_var: Optional[Parameter] = None, override: bool = True, **kwargs: Any
    ) -> Optional[pn.panel]:
        """Generates a violin plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a violin plot
        and then passes the filtered data to to_violin_ds for rendering.

        Args:
            result_var (Optional[Parameter]): The result variable to plot. If None, uses the default.
            override (bool): Whether to override filter restrictions. Defaults to True.
            **kwargs (Any): Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the violin plot if data is appropriate,
            otherwise returns filter match results.
        """
        return self.to_distribution_plot(
            self.to_violin_ds,
            result_var=result_var,
            override=override,
            **kwargs,
        )

    def to_violin_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs: Any) -> hv.Violin:
        """Creates a violin plot from the provided dataset.

        Given a filtered dataset, this method generates a violin plot visualization showing
        the distribution of values for a result variable, potentially grouped by a categorical variable.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs (Any): Additional keyword arguments for plot customization, such as:
                      - violin_color: Color for the violin body
                      - inner_color: Color for inner statistics markers
                      - line_width: Width of outline lines
                      - bandwidth: Controls the smoothness of the density estimate

        Returns:
            hv.Violin: A HoloViews Violin plot of the benchmark data.
        """
        return self._plot_distribution(dataset, result_var, hv.Violin, **kwargs)
