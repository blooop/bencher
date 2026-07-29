from __future__ import annotations

import panel as pn
from param import Parameter

from bencher.results.bench_result_base import BenchResultBase
from bencher.results.video_controls import VideoControls
from bencher.variables.results import (
    PANEL_TYPES,
)


class PaneResult(BenchResultBase):
    def to_video(self, result_var: Parameter | None = None, **kwargs):
        vc = VideoControls()
        return pn.Column(
            vc.video_controls(),
            self.to_panes(result_var=result_var, container=vc.video_container, **kwargs),
        )

    def to_panes(
        self,
        result_var: Parameter | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        container=None,
        subsampling_divisions: int | None = None,
        **kwargs,
    ) -> pn.pane.panel | None:
        return self.map_sample_panes(
            PANEL_TYPES,
            container=container,
            result_var=result_var,
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            subsampling_divisions=subsampling_divisions,
            **kwargs,
        )
