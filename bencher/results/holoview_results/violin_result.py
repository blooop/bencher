from __future__ import annotations
from typing import Optional, TYPE_CHECKING
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

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    pass


class ViolinResult(HoloviewResult):
    """A class for creating violin plots from benchmark results.

    Violin plots combine aspects of box plots with kernel density plots, showing
    the distribution shape of the data. This class provides methods to generate
    these plots from benchmark data, which is particularly useful for visualizing
    the distribution of metrics across different configurations or repetitions.
    """

    @staticmethod
    def from_bench_result(bench_result):
        """Get a violin plot directly from a BenchResult.

        Args:
            bench_result: The BenchResult to create a violin plot from

        Returns:
            func: A function that creates a violin plot when called with a result_var
        """

        # Define a wrapper function that handles the violin plot creation
        def get_violin_plot(result_var=None, **kwargs):
            override = kwargs.pop("override", True)

            # Create a plot callback that accepts exactly what filter will pass to it
            def plot_callback(dataset, result_var=result_var, **kwargs):
                return dataset[result_var.name].hvplot.violin(
                    y=result_var.name, title=f"{result_var.name} Distribution", **kwargs
                )

            # Use the result's filter method which will properly handle the dataset
            return bench_result.filter(
                plot_callback,
                float_range=VarRange(0, 0),
                cat_range=VarRange(0, None),
                repeats_range=VarRange(2, None),
                reduce=ReduceType.NONE,
                target_dimension=2,
                result_var=result_var,
                result_types=(ResultVar),
                override=override,
            )

        return get_violin_plot

    def to_violin(
        self, result_var: Parameter = None, override: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        """Generates a violin plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a violin plot
        and then passes the filtered data to to_violin_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the violin plot if data is appropriate,
                              otherwise returns filter match results.
        """
        return self.filter(
            self.to_violin_ds,
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

    def to_violin_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs) -> hv.Violin:
        """Creates a violin plot from the provided dataset.

        Given a filtered dataset, this method generates a violin plot visualization showing
        the distribution of values for a result variable, potentially grouped by a categorical variable.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the violin plot options.

        Returns:
            hv.Violin: A HoloViews Violin plot of the benchmark data.
        """
        by = None
        if hasattr(self, "plt_cnt_cfg") and self.plt_cnt_cfg.cat_cnt >= 2:
            by = self.plt_cnt_cfg.cat_vars[1].name
        da_plot = dataset[result_var.name]
        title = (
            self.title_from_ds(da_plot, result_var, **kwargs)
            if hasattr(self, "title_from_ds")
            else f"{result_var.name} Distribution"
        )
        time_widget_args = (
            self.time_widget(title) if hasattr(self, "time_widget") else {"title": title}
        )
        return da_plot.hvplot.violin(y=result_var.name, by=by, **time_widget_args, **kwargs)
