from __future__ import annotations

from typing import Any

import holoviews as hv

from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult


class TableResult(HoloviewResult):
    def to_plot(self, **_kwargs: Any) -> hv.Table:
        """Convert the dataset to a Table visualization.

        Returns:
            hv.Table: A HoloViews Table object.
        """
        return self.to_hv_type(hv.Table, ReduceType.SQUEEZE)
