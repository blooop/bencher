from __future__ import annotations

import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultFloat


class HistogramResult(HoloviewResult):
    """Histogram plots using Plotly."""

    def to_plot(self, result_var=None, target_dimension=2, **kwargs):
        return self.filter(
            self.to_histogram_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            input_range=VarRange(0, 0),
            reduce=ReduceType.NONE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultFloat,),
            **kwargs,
        )

    def _make_histogram(self, dataset: xr.Dataset, result_var: Parameter, **_kwargs):
        var = result_var.name
        values = dataset[var].values.ravel()
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=values,
                name=var,
                marker_color="#636EFA",
            )
        )
        fig.update_layout(
            title=f"{var} vs Count",
            xaxis_title=var,
            yaxis_title="count",
            width=600,
            height=500,
            margin=dict(t=60, b=60, r=40, l=60),
            template="plotly_white",
        )
        return fig

    def to_histogram_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs):
        if self._use_holomap_for_time(dataset):
            da = dataset[result_var.name]

            def make_hist(da_window):
                ds = da_window.to_dataset()
                return self._make_histogram(ds, result_var, **kwargs)

            return self._build_time_holomap_raw(da, make_hist)

        return self._make_histogram(dataset, result_var, **kwargs)
