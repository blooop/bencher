from __future__ import annotations

import plotly.graph_objects as go
from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult


class TableResult(HoloviewResult):
    def to_plot(self, **kwargs):
        """Convert the dataset to a Plotly Table visualization."""
        ds = self.to_dataset(ReduceType.SQUEEZE)
        df = ds.to_dataframe().reset_index()

        fig = go.Figure(data=[go.Table(
            header=dict(values=list(df.columns)),
            cells=dict(values=[df[col] for col in df.columns]),
        )])
        fig.update_layout(width=800, height=400, margin=dict(t=30, b=10, r=10, l=10))
        return fig
