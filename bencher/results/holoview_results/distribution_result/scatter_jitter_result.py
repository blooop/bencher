from __future__ import annotations

from typing import Any

import holoviews as hv
import panel as pn
import xarray as xr
from param import Parameter

from bencher.plotting.plot_filter import VarRange
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.distribution_result.distribution_result import (
    DistributionResult,
)
from bencher.results.holoview_results.holoview_result import PlotResult
from bencher.variables.results import ResultFloat


class ScatterJitterResult(DistributionResult):
    """A class for creating scatter jitter plots from benchmark results.

    Scatter jitter plots display individual data points with slight random offsets
    to avoid overlapping, making it easier to visualize the distribution of data.
    This is particularly useful for smaller datasets where showing individual points
    provides more insight than aggregate statistics, or alongside box plots to show
    the actual data distribution.

    Key features:
    - Displays individual data points rather than statistical summaries
    - Applies controlled random offsets to avoid point overlap
    - Useful for revealing the actual sample size and distribution
    - Complements statistical plots like box plots or violin plots
    """

    def to_plot(
        self,
        result_var: Parameter | None = None,
        override: bool = True,
        jitter: float = 0.1,
        target_dimension: int | None = None,
        **kwargs: Any,
    ) -> pn.panel | None:
        """Generates a scatter jitter plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a scatter plot
        and then passes the filtered data to to_scatter_jitter_ds for rendering.

        Args:
            result_var: The result variable to plot. If None, uses the default.
            override: Whether to override filter restrictions. Defaults to True.
            jitter: Amount of jitter to apply to points. Defaults to 0.1.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            A panel containing the scatter jitter plot if data is appropriate,
            otherwise returns filter match results.
        """
        if target_dimension is None:
            # +1 cos we have a repeats dimension
            target_dimension = self.plt_cnt_cfg.cat_cnt + 1
        return self.filter(
            self.to_scatter_jitter_ds,
            float_range=VarRange.exactly(0),
            cat_range=VarRange.at_most(1),
            repeats_range=VarRange.at_least(2),
            reduce=ReduceType.NONE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultFloat,),
            override=override,
            jitter=jitter,
            **kwargs,
        )

    def to_scatter_jitter_ds(
        self, dataset: xr.Dataset, result_var: Parameter, jitter: float = 0.1, **kwargs: Any
    ) -> PlotResult:
        """Creates a scatter jitter plot from the provided dataset.

        Given a filtered dataset, this method generates a scatter visualization showing
        individual data points with random jitter to avoid overlapping, making the
        distribution of values more visible.

        Args:
            dataset: The dataset containing benchmark results.
            result_var: The result variable to plot.
            jitter: Amount of jitter to apply to points. Defaults to 0.1.
            **kwargs: Additional keyword arguments for plot customization, such as:
                      - color: Color for data points
                      - size: Size of data points
                      - alpha: Transparency of data points
                      - marker: Shape of data points ('o', 's', 'd', etc.)

        Returns:
            An ``hv.Overlay`` wrapping the jittered Scatter, or a panel layout for an
            over_time dataset (see ``PlotResult``). See ``_plot_distribution``
            (plan 23 P12) for why the previous ``hv.Scatter`` annotation was never
            satisfied.
        """
        # Prepare the data using the common method from the parent class
        return self._plot_distribution(dataset, result_var, hv.Scatter, jitter=jitter, **kwargs)
