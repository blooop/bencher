from __future__ import annotations
import panel as pn
from param import Parameter
from functools import partial
import hvplot.xarray  # noqa pylint: disable=duplicate-code,unused-import
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import SCALAR_RESULT_TYPES
from bencher.results.holoview_results.holoview_result import HoloviewResult, use_tap


class LineResult(HoloviewResult):
    """A class for creating line plot visualizations from benchmark results.

    Line plots are effective for visualizing trends in data over a continuous variable.
    This class provides methods to generate interactive line plots from benchmark data,
    with options for adding interactive tap functionality to display detailed information
    about specific data points.
    """

    def to_plot(self, **kwargs) -> pn.panel | None:
        """Generates a line plot. See ``to_line`` for parameters."""
        return self.to_line(**kwargs)

    def to_line(
        self,
        result_var: Parameter | None = None,
        tap_var=None,
        tap_container: pn.pane.panel = None,
        target_dimension=2,
        override: bool = True,
        use_tap: bool = use_tap,
        **kwargs,
    ) -> pn.panel | None:
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
            pn.panel | None: A panel containing the line plot, or filter match results.
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

        # When over_time is active, also accept 0 float vars so a 0D benchmark
        # gets a time-series line (x=over_time, y=value).
        if self.bench_cfg.over_time:
            float_range = VarRange(0, 1)
            input_range = VarRange(0, None)
        else:
            float_range = VarRange(1, 1)
            input_range = None
        return self.filter(
            line_cb,
            float_range=float_range,
            cat_range=VarRange(0, None),
            repeats_range=VarRange(1, 1),
            panel_range=VarRange(0, None),
            input_range=input_range,
            reduce=ReduceType.SQUEEZE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=SCALAR_RESULT_TYPES,
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
        da_plot = dataset[result_var.name]

        # 0D + over_time: time-series line with time on the x-axis.
        # This is a standalone chart (not a HoloMap) since it inherently
        # shows all time points at once.
        if not self.plt_cnt_cfg.float_vars and "over_time" in da_plot.dims:
            title = self.title_from_ds(da_plot, result_var, **kwargs)
            plot = da_plot.hvplot.line(
                x="over_time",
                y=da_plot.name,
                title=title,
                widget_location="bottom",
                **kwargs,
            )
            return self._apply_opts(plot, xrotation=30)

        # No float vars and over_time was squeezed (single time point) — no x-axis
        if not self.plt_cnt_cfg.float_vars:
            return None

        x = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        title = self.title_from_ds(da_plot, result_var, **kwargs)

        if self._use_holomap_for_time(dataset):

            def make_line(ds_t):
                # When _std exists (e.g. after _mean_over_time aggregation),
                # delegate to the curve overlay which renders Spread bands.
                std_var = f"{result_var.name}_std"
                if std_var in ds_t.data_vars:
                    return self._build_curve_overlay(ds_t, result_var, **kwargs)
                da_t = ds_t[result_var.name]
                plot_t = da_t.hvplot.line(x=x, by=by, title=title, **kwargs)
                return self._apply_opts(plot_t, xrotation=30)

            return self._build_time_holomap(dataset, result_var.name, make_line)

        time_widget_args = self.time_widget(title)
        plot = da_plot.hvplot.line(
            x=x, by=by, widget_location="bottom", **time_widget_args, **kwargs
        )
        return self._apply_opts(plot, xrotation=30)

    def _to_line_tap_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        result_var_plots: list[Parameter] | None = None,
        container: pn.pane.panel = pn.pane.panel,
        **kwargs,
    ) -> pn.Row:
        """Creates an interactive line plot with tap functionality.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The primary result variable to plot.
            result_var_plots (list[Parameter], optional): Additional result variables
                to display when a point is tapped.
            container (pn.pane.panel, optional): Container to display tapped information.
            **kwargs: Additional keyword arguments passed to the line plot options.

        Returns:
            pn.Row: A panel row containing the interactive line plot and tap info.
        """
        da_plot = dataset[result_var.name]
        x = self.plt_cnt_cfg.float_vars[0].name
        by = None
        if self.plt_cnt_cfg.cat_cnt >= 1:
            by = self.plt_cnt_cfg.cat_vars[0].name
        title = self.title_from_ds(da_plot, result_var, **kwargs)
        plot = da_plot.hvplot.line(x=x, by=by, title=title, **kwargs).opts(
            tools=["hover"], xrotation=30
        )
        return self._build_tap_plot(plot, dataset, result_var_plots, container)
