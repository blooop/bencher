from __future__ import annotations

from typing import Callable, Any
import plotly.graph_objects as go
from param import Parameter
import xarray as xr

from bencher.results.bench_result_base import ReduceType
from bencher.plotting.plot_filter import VarRange
from bencher.variables.results import ResultFloat
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.utils import params_to_str


class DistributionResult(HoloviewResult):
    """Base class for distribution plots (violin, box, scatter jitter) using Plotly."""

    def to_distribution_plot(
        self,
        plot_method: Callable,
        result_var: Parameter | None = None,
        override: bool = True,
        **kwargs: Any,
    ):
        return self.filter(
            plot_method,
            float_range=VarRange(0, 0),
            cat_range=VarRange(0, None),
            repeats_range=VarRange(2, None),
            reduce=ReduceType.NONE,
            target_dimension=self.plt_cnt_cfg.cat_cnt + 1,
            result_var=result_var,
            result_types=(ResultFloat,),
            override=override,
            **kwargs,
        )

    def _plot_distribution(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        plot_type: str,
        **kwargs: Any,
    ) -> go.Figure:
        """Create a distribution plot (violin, box, or scatter).

        Args:
            dataset: The dataset containing benchmark results.
            result_var: The result variable to plot.
            plot_type: One of "violin", "box", "scatter".
            **kwargs: Additional keyword arguments.

        Returns:
            A Plotly Figure with the distribution plot.
        """
        var_name = result_var.name
        title = self.title_from_ds(dataset[var_name], result_var, **kwargs)
        cat_names = params_to_str(self.plt_cnt_cfg.cat_vars)

        use_holomap = self._use_holomap_for_time(dataset)

        if use_holomap:
            da = dataset[var_name]

            def make_dist(da_window):
                df = da_window.to_dataframe().reset_index()
                return self._build_distribution_fig(
                    df, plot_type, cat_names, var_name, result_var, title, **kwargs
                )

            return self._build_time_holomap_raw(da, make_dist)

        df = dataset[var_name].to_dataframe().reset_index()
        return self._build_distribution_fig(
            df, plot_type, cat_names, var_name, result_var, title, **kwargs
        )

    @staticmethod
    def _build_distribution_fig(df, plot_type, cat_names, var_name, result_var, title, **kwargs):
        """Build a Plotly figure for distribution data."""
        fig = go.Figure()

        # Determine grouping
        x_col = cat_names[0] if cat_names else None

        jitter = kwargs.pop("jitter", 0.1)

        if plot_type == "violin":
            if x_col and x_col in df.columns:
                for val in df[x_col].unique():
                    subset = df[df[x_col] == val]
                    fig.add_trace(
                        go.Violin(
                            y=subset[var_name],
                            name=str(val),
                            box_visible=True,
                            meanline_visible=True,
                        )
                    )
            else:
                fig.add_trace(
                    go.Violin(
                        y=df[var_name],
                        name=var_name,
                        box_visible=True,
                        meanline_visible=True,
                    )
                )

        elif plot_type == "box":
            if x_col and x_col in df.columns:
                for val in df[x_col].unique():
                    subset = df[df[x_col] == val]
                    fig.add_trace(
                        go.Box(
                            y=subset[var_name],
                            name=str(val),
                            boxmean="sd",
                        )
                    )
            else:
                fig.add_trace(
                    go.Box(
                        y=df[var_name],
                        name=var_name,
                        boxmean="sd",
                    )
                )

        elif plot_type == "scatter":
            if x_col and x_col in df.columns:
                for val in df[x_col].unique():
                    subset = df[df[x_col] == val]
                    fig.add_trace(
                        go.Box(
                            y=subset[var_name],
                            name=str(val),
                            boxpoints="all",
                            jitter=jitter,
                            pointpos=0,
                            line=dict(color="rgba(0,0,0,0)"),
                            fillcolor="rgba(0,0,0,0)",
                            marker=dict(size=4, opacity=0.5),
                        )
                    )
            else:
                fig.add_trace(
                    go.Box(
                        y=df[var_name],
                        name=var_name,
                        boxpoints="all",
                        jitter=jitter,
                        pointpos=0,
                        line=dict(color="rgba(0,0,0,0)"),
                        fillcolor="rgba(0,0,0,0)",
                        marker=dict(size=4, opacity=0.5),
                    )
                )

        fig.update_layout(
            title=title,
            yaxis_title=f"{var_name} [{getattr(result_var, 'units', '')}]",
            width=600,
            height=500,
            margin=dict(t=60, b=60, r=40, l=60),
            template="plotly_white",
        )
        if x_col:
            fig.update_layout(xaxis_title=x_col)
        return fig
