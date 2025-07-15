from typing import Optional
from functools import partial

import panel as pn
from param import Parameter
import holoviews as hv

from bencher.variables.results import PANEL_TYPES
from bencher.results.bench_result_base import BenchResultBase, ReduceType


class DataSetResult(BenchResultBase):
    def to_plot(
        self,
        result_var: Parameter = None,
        hv_dataset=None,
        target_dimension: int = 0,
        container=None,
        level: int = None,
        **kwargs,
    ) -> Optional[pn.pane.panel]:
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(ReduceType.SQUEEZE, level=level)
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)
        return self.map_plot_panes(
            partial(self.ds_to_container, container=container),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=PANEL_TYPES,
            **kwargs,
        )
