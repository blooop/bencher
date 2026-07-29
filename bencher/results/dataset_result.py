from __future__ import annotations

from collections.abc import Callable
from typing import Any

import panel as pn
from param import Parameter

from bencher.results.bench_result_base import BenchResultBase
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

    A thin naming of ``map_sample_panes`` restricted to ``ResultDataSet``: the
    pane-type render path itself is shared with ``PaneResult.to_panes``, which is
    what the default report actually goes through, so a chart type composing this
    behaves identically to a declared ``container=``.
    """
    return result.map_sample_panes(
        (ResultDataSet,),
        container=renderer,
        result_var=result_var,
        hv_dataset=hv_dataset,
        target_dimension=target_dimension,
        subsampling_divisions=subsampling_divisions,
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
