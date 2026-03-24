from __future__ import annotations

from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultVar, ResultBool
from bencher.results.holoview_results.holoview_result import HoloviewResult


class CurveResult(HoloviewResult):
    """Curve plots (line + error bands) using Plotly."""

    def to_plot(self, result_var=None, override=True, **kwargs):
        return self.to_curve(result_var=result_var, override=override, **kwargs)

    def to_curve(self, result_var=None, override=True, target_dimension=2, **kwargs):
        return self.filter(
            self.to_curve_ds,
            float_range=VarRange(1, 1),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.REDUCE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar, ResultBool),
            override=override,
            **kwargs,
        )

    def to_curve_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        if self._use_holomap_for_time(dataset):

            def make_curve(ds_t):
                return self._build_curve_overlay(ds_t, result_var, **kwargs)

            return self._build_time_holomap(dataset, result_var.name, make_curve)

        return self._build_curve_overlay(dataset, result_var, **kwargs)
