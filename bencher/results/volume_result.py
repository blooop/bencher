from typing import Optional, Any

import xarray as xr
from param import Parameter
import panel as pn
import plotly.graph_objs as go

from bencher.plotting.plot_filter import VarRange
from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.variables.results import ResultVar


class VolumeResult(BenchResultBase):
    def to_plot(
        self, result_var: Optional[Parameter] = None, override: bool = True, **kwargs: Any
    ) -> Optional[pn.panel]:
        """Generates a 3d volume plot from benchmark data.

        Args:
            result_var (Optional[Parameter]): The result variable to plot. If None, uses the default.
            override (bool): Whether to override filter restrictions. Defaults to True.
            **kwargs (Any): Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.panel]: A panel containing the volume plot if data is appropriate,
            otherwise returns filter match results.
        """
        return self.to_volume(
            result_var=result_var,
            override=override,
            **kwargs,
        )

    def to_volume(
        self,
        result_var: Parameter = None,
        override: bool = True,
        target_dimension: int = 3,
        **kwargs,
    ):
        """Generates a 3D volume plot from benchmark data.

        This method applies filters to ensure the data is appropriate for a volume plot
        and then passes the filtered data to to_volume_ds for rendering.

        Args:
            result_var (Parameter, optional): The result variable to plot. If None, uses the default.
            override (bool, optional): Whether to override filter restrictions. Defaults to True.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 3.
            **kwargs: Additional keyword arguments passed to the plot rendering.

        Returns:
            Optional[pn.pane.Plotly]: A panel containing the volume plot if data is appropriate,
                                    otherwise returns filter match results.
        """
        return self.filter(
            self.to_volume_ds,
            float_range=VarRange(3, 3),
            cat_range=VarRange(-1, 0),
            reduce=ReduceType.REDUCE,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultVar),
            override=override,
            **kwargs,
        )

    def to_volume_ds(
        self, dataset: xr.Dataset, result_var: Parameter, width=600, height=600
    ) -> Optional[pn.pane.Plotly]:
        """Given a benchCfg generate a 3D surface plot
        Returns:
            pn.pane.Plotly: A 3d volume plot as a holoview in a pane
        """
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

        layout = go.Layout(
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

        fig = dict(data=data, layout=layout)

        return pn.pane.Plotly(fig, name="volume_plotly")
