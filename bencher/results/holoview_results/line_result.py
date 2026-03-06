from __future__ import annotations
from typing import List, Optional
import panel as pn
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class LineResult(HoloviewResult):
    """A class for creating line plot visualizations from benchmark results.

    Line plots are effective for visualizing trends in data over a continuous variable.
    This class provides methods to generate interactive line plots from benchmark data,
    with options for adding interactive tap functionality to display detailed information
    about specific data points.
    """

    def to_plot(self, **kwargs) -> Optional[pn.panel]:
        """Generates a line plot. See ``to_line`` for parameters."""
        return self.to_line(**kwargs)

    def to_line(
        self,
        result_var: Parameter | None = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool | None = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Generates a line plot from benchmark data.

        Args:
            result_var (Parameter, optional): The result variable to plot.
            tap_var: Variables to display when tapping on line plot points.
            tap_container (pn.pane.panel, optional): Container to hold tapped information.
            target_dimension (int, optional): Target dimensionality for the plot. Defaults to 2.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            use_tap (bool, optional): Whether to enable tap functionality.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the line plot, or filter match results.
        """
        if tap_var is None:
            tap_var = self.plt_cnt_cfg.panel_vars
        elif not isinstance(tap_var, list):
            tap_var = [tap_var]

        if len(tap_var) == 0 or self.plt_cnt_cfg.inputs_cnt > 1 or not use_tap:
            line_cb = self.to_line_ds
        else:
            line_cb = partial(
                self._to_line_tap_ds, result_var_plots=tap_var, container=tap_container
            )

        return self.filter(
            line_cb,
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            panel_range=VarRange(0, None),
            reduce=ReduceType.SQUEEZE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar, ResultBool),
            override=override,
            **kwargs,
        )

    def to_line_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        """Creates a basic line plot from the provided dataset.

        When over_time is active with multiple time points, creates an hv.HoloMap
        with a slider.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the line plot options.

        Returns:
            hvplot.element.Curve | pn.Column: A line plot visualization.
        """
        x = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        da_plot = dataset[result_var.name]
        title = self.title_from_ds(da_plot, result_var, **kwargs)

        time_plot = self._build_time_holomap(
            dataset, result_var, lambda da_t: da_t.hvplot.line(x=x, by=by, title=title, **kwargs)
        )
        if time_plot is not None:
            return time_plot

        return da_plot.hvplot.line(x=x, by=by, **self.time_widget(title), **kwargs)

    def _to_line_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: List[Parameter] | None = None,
        container: pn.pane.panel = pn.pane.panel,
        **kwargs,
    ) -> pn.Row:
        """Creates an interactive line plot with tap functionality.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The primary result variable to plot.
            result_var_plots (List[Parameter], optional): Additional result variables
                to display when a point is tapped.
            container (pn.pane.panel, optional): Container to display tapped information.
            **kwargs: Additional keyword arguments passed to the line plot options.

        Returns:
            pn.Row: A panel row containing the interactive line plot and tap info.
        """
        plot = self.to_line_ds(dataset, result_var).opts(tools=["hover"], **kwargs)
        return self._build_tap_plot(plot, dataset, result_var_plots, container)
