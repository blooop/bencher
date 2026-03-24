from __future__ import annotations

from typing import Any
from param import Parameter
import xarray as xr

from bencher.results.holoview_results.distribution_result.distribution_result import (
    DistributionResult,
)


class ViolinResult(DistributionResult):
    """Violin plots using Plotly."""

    def to_plot(self, result_var=None, override=True, **kwargs: Any):
        return self.to_distribution_plot(
            self.to_violin_ds,
            result_var=result_var,
            override=override,
            **kwargs,
        )

    def to_violin_ds(self, dataset: xr.Dataset, result_var: Parameter, **kwargs: Any):
        return self._plot_distribution(dataset, result_var, "violin", **kwargs)
