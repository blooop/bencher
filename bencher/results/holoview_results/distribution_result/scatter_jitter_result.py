from __future__ import annotations

from typing import Any
from param import Parameter
import xarray as xr

from bencher.results.holoview_results.distribution_result.distribution_result import (
    DistributionResult,
)
from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultFloat


class ScatterJitterResult(DistributionResult):
    """Scatter jitter plots using Plotly."""

    def to_plot(
        self,
        result_var=None,
        override=True,
        jitter=0.1,
        target_dimension=None,
        **kwargs: Any,
    ):
        if target_dimension is None:
            target_dimension = self.plt_cnt_cfg.cat_cnt + 1
        return self.filter(
            self.to_scatter_jitter_ds,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, 1),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.NONE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultFloat,),
            override=override,
            jitter=jitter,
            **kwargs,
        )

    def to_scatter_jitter_ds(
        self, dataset: xr.Dataset, result_var: Parameter, jitter=0.1, **kwargs: Any
    ):
        return self._plot_distribution(dataset, result_var, "scatter", jitter=jitter, **kwargs)
