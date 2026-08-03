from __future__ import annotations

import holoviews as hv
import hvplot.xarray  # noqa: F401  # pylint: disable=duplicate-code,unused-import
import xarray as xr
from param import Parameter

from bencher.plotting.plot_filter import VarRange
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult, PlotResult
from bencher.variables.results import SCALAR_RESULT_TYPES


class CurveResult(HoloviewResult):
    """A class for creating curve plots with optional standard-deviation spread.

    Curve plots show the relationship between a continuous input variable and a
    result variable.  When multiple benchmark repetitions are available, standard
    deviation bounds are displayed using an ``hv.Spread`` overlay.
    """

    def to_plot(self, **kwargs) -> hv.Curve | None:
        """Generates a curve plot. See ``to_curve`` for parameters."""
        return self.to_curve(**kwargs)

    def to_curve(
        self, result_var: Parameter | None = None, override: bool = True, **kwargs
    ) -> hv.Curve | None:
        """Generates a curve plot from benchmark data.

        Args:
            result_var (Parameter, optional): The result variable to plot.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            hv.Curve | None: A curve plot, or filter match results.
        """
        return self.filter(
            self.to_curve_ds,
            float_range=VarRange.exactly(1),
            cat_range=VarRange.unbounded(),
            repeats_range=VarRange.at_least(2),
            reduce=ReduceType.REDUCE,
            target_dimension=2,
            result_var=result_var,
            result_types=SCALAR_RESULT_TYPES,
            override=override,
            **kwargs,
        )

    def to_curve_ds(
        self, dataset: xr.Dataset, result_var: Parameter, **kwargs
    ) -> PlotResult | None:
        """Creates a curve plot from the provided dataset.

        Generates a curve with optional standard deviation spread overlay.

        When over_time is active with multiple time points, builds per-time-point
        curves inside an hv.HoloMap so the slider controls the time dimension.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            **kwargs: Additional keyword arguments passed to the curve plot options.

        Returns:
            An ``hv.Overlay`` of the curve plus optional standard-deviation spread, or a
            panel layout when over_time wraps it for the time slider (see
            ``PlotResult``); ``None`` for a dataset with no dimensions, since there is
            nothing to put on an axis. Never a bare ``hv.Curve``:
            ``_build_curve_overlay`` composes into an Overlay whenever it returns at all.
        """
        if self._use_holomap_for_time(dataset):
            var = result_var.name

            def make_curve(ds_t):
                return self._build_curve_overlay(ds_t, result_var, **kwargs)

            return self._build_time_holomap(dataset, var, make_curve)

        return self._build_curve_overlay(dataset, result_var, **kwargs)
