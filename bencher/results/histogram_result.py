from __future__ import annotations
import panel as pn
from param import Parameter
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import hvplot.pandas  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult

from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultFloat


class HistogramResult(HoloviewResult):
    def to_plot(
        self, result_var: Parameter | None = None, target_dimension: int = 2, **kwargs
    ) -> pn.pane.Pane | None:
        """Generates a histogram plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a histogram
        and then passes the filtered data to to_histogram_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 2.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            pn.pane.Pane | None: A panel containing the histogram if data is appropriate,
                                  otherwise returns filter match results.
        """
        return self.filter(
            self.to_histogram_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            panel_range=VarRange(0, None),
            input_range=VarRange(0, 0),
            reduce=ReduceType.NONE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultFloat,),
            **kwargs,
        )

    def _make_histogram(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        """Render a single histogram from a dataset (no over_time handling)."""
        plot = dataset.hvplot(
            kind="hist",
            y=[result_var.name],
            ylabel="count",
            legend="bottom_right",
            title=f"{result_var.name} vs Count",
            **kwargs,
        )
        return self._apply_opts(plot, xrotation=30)

    def to_histogram_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        """Creates a histogram from the provided dataset.

        Given a filtered dataset, this method generates a histogram visualization showing
        the distribution of values for the result variable. When over_time is active with
        multiple time points, produces per-time-point and pooled-aggregate tabs.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot in the histogram.
            **kwargs: Additional keyword arguments passed to the histogram plot options.

        Returns:
            hvplot.element.Histogram: A histogram visualization of the benchmark data distribution.
        """
        if self._use_holomap_for_time(dataset):
            da = dataset[result_var.name]

            def make_hist(da_window):
                ds = da_window.to_dataset()
                return self._make_histogram(ds, result_var, **kwargs)

            return self._build_time_holomap_raw(da, make_hist)

        return self._make_histogram(dataset, result_var, **kwargs)
