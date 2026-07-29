from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

import holoviews as hv
import panel as pn
from param import Parameter

from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.variables.results import ResultDataSet


def render_data_samples(
    result: BenchResultBase,
    renderer: Callable[[Any], Any] | None = None,
    result_var: Parameter | None = None,
    hv_dataset=None,
    target_dimension: int = 0,
    subsampling_divisions: int | None = None,
    **kwargs: Any,
) -> pn.pane.panel | None:
    """Map an optional renderer over each stored ``ResultDataSet`` payload.

    Storage is deliberately payload-agnostic. The renderer, when supplied, owns
    every interpretation of the object (tabular, image-like, domain specific,
    and so on); without one, the stored object is handed to Panel.
    """
    if hv_dataset is None:
        hv_dataset = result.to_hv_dataset(
            ReduceType.SQUEEZE, subsampling_divisions=subsampling_divisions
        )
    elif not isinstance(hv_dataset, hv.Dataset):
        hv_dataset = hv.Dataset(hv_dataset)
    return result.map_plot_panes(
        partial(result.ds_to_container, container=renderer),
        hv_dataset=hv_dataset,
        target_dimension=target_dimension,
        result_var=result_var,
        result_types=(ResultDataSet,),
        **kwargs,
    )


class DataSetResult(BenchResultBase):
    """Render the arbitrary per-sample payloads stored by ``ResultDataSet``."""

    def to_plot(
        self,
        result_var: Parameter | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        container: Callable[[Any], Any] | None = None,
        subsampling_divisions: int | None = None,
        **kwargs: Any,
    ) -> pn.pane.panel | None:
        """Render stored payloads, preserving the public ``container=`` API."""
        return render_data_samples(
            self,
            renderer=container,
            result_var=result_var,
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            subsampling_divisions=subsampling_divisions,
            **kwargs,
        )
