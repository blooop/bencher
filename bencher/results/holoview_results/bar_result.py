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
        self, result_var: Parameter | None = None, override: bool = True, **kwargs
    ) -> Optional[pn.panel]:
        return self.to_bar(result_var, override, **kwargs)

    def to_bar(
        self,
        result_var: Parameter | None = None,
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
        # When over_time is active, allow 0 inputs so 0D+0cat+over_time can produce
        # a line chart.  Without over_time, require at least 1 input (the default).
        input_range = VarRange(0, None) if self.bench_cfg.over_time else None
        common = {
            "float_range": VarRange(0, 0),
            "cat_range": VarRange(0, None),
            "panel_range": VarRange(0, None),
            "input_range": input_range,
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

    def to_bar_ds(self, dataset: xr.Dataset, result_var: Parameter | None = None, **kwargs):
        """Creates a bar chart from the provided dataset.

        Given a filtered dataset, this method generates a bar chart visualization showing
        values of the result variable, potentially grouped by categorical variables.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            **kwargs: Additional keyword arguments passed to the bar chart options.

        Returns:
            hvplot.element.Bars | hv.HoloMap: A bar chart visualization of the benchmark data.
        """
        da = dataset[result_var.name]
        use_holomap = self._use_holomap_for_time(dataset)

        # Allow explicit override via kwargs
        by = kwargs.pop("by", None)

        # Determine x-axis and by grouping from non-over_time dims
        non_time_dims = [d for d in da.dims if d not in ("repeat", "over_time")]
        if by is None:
            cat_dim_names = [cv.name for cv in self.plt_cnt_cfg.cat_vars]
            x_dim = non_time_dims[0] if non_time_dims else "over_time"
            candidates = [d for d in non_time_dims if d != x_dim and d in cat_dim_names]

            if len(candidates) == 1:
                by = candidates[0]
            elif len(candidates) > 1:
                by = candidates
            else:
                by = None
        else:
            x_dim = non_time_dims[0] if non_time_dims else "over_time"

        title = self.title_from_ds(da, result_var, **kwargs)
        opts_kwargs = dict(
            title=title, ylabel=f"{da.name} [{result_var.units}]", xrotation=30, **kwargs
        )

        if not non_time_dims and "over_time" in da.dims:
            if use_holomap:
                # 0D + 0cat + over_time (multiple time points): line chart with time on x-axis.
                plot = da.hvplot.line(x="over_time", y=da.name, title=title, **kwargs)
                if hasattr(plot, "opts"):
                    plot = plot.opts(**opts_kwargs)
                return plot
            # 0D + single time point: nothing meaningful to bar-chart.
            return None

        # No over_time slider needed: either no over_time, single time point,
        # or over_time is the only dim (used as x-axis directly).
        plot = da.hvplot.bar(x=x_dim, y=da.name, by=by, title=title, **kwargs)
        if hasattr(plot, "opts"):
            plot = plot.opts(**opts_kwargs)
        return plot
