from __future__ import annotations

import logging
from typing import Any

import xarray as xr
from param import Parameter
import plotly.graph_objects as go

from bencher.plotting.plot_filter import VarRange
from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.variables.results import ResultVar


class VolumeResult(BenchResultBase):
    def to_plot(self, result_var=None, override=True, **kwargs: Any):
        return self.to_volume(result_var=result_var, override=override, **kwargs)

    def to_volume(self, result_var=None, override=True, target_dimension=3, **kwargs):
        if self.bench_cfg.over_time:
            logging.info("Volume plots are not supported with over_time; skipping")
            return None
        return self.filter(
            self.to_volume_ds,
            float_range=VarRange(3, 3),
            cat_range=VarRange(-1, 0),
            reduce=ReduceType.REDUCE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar,),
            override=override,
            **kwargs,
        )

    def to_volume_ds(self, dataset: xr.Dataset, result_var: Parameter, width=600, height=600):
        x = self.bench_cfg.input_vars[0]
        y = self.bench_cfg.input_vars[1]
        z = self.bench_cfg.input_vars[2]
        opacity = 0.1
        meandf = dataset[result_var.name].to_dataframe().reset_index()
        data = [
            go.Volume(
                x=meandf[x.name],
                y=meandf[y.name],
                z=meandf[z.name],
                value=meandf[result_var.name],
                isomin=meandf[result_var.name].min(),
                isomax=meandf[result_var.name].max(),
                opacity=opacity,
                surface_count=20,
            )
        ]

        fig = go.Figure(data=data)
        fig.update_layout(
            title=f"{result_var.name} vs ({x.name} vs {y.name} vs {z.name})",
            width=width,
            height=height,
            margin=dict(t=50, b=50, r=50, l=50),
            scene=dict(
                xaxis_title=f"{x.name} [{x.units}]",
                yaxis_title=f"{y.name} [{y.units}]",
                zaxis_title=f"{z.name} [{z.units}]",
            ),
        )
        return fig
