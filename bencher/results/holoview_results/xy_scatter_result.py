"""Scatter two *measured* columns of a tabular result against each other.

Every other scatter in bencher puts an input variable on x and a result variable on
y: one point per sample. This one plots inside a single sample — a ``ResultDataSet``
whose rows are the measurement (landing points, hit locations, a phase-space cloud),
where both axes are things the benchmark measured and the sweep dimensions are what
separate one plot from the next.

Two ways in, same renderer:

* declaratively, so the cloud renders with the other results in ``result_vars`` order::

      cloud = bn.ResultDataSet(container=bn.xy_scatter(x="dx_mm", y="dy_mm"))

* explicitly, for a report-level plot::

      bench.add(bn.XYScatterResult, x="dx_mm", y="dy_mm", color="index")

See :mod:`bencher.results.holoview_results.tabular_spec` for the machinery this and
the other intra-sample charts share.
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import holoviews as hv
import panel as pn
from param import Parameter

from bencher.results.holoview_results.tabular_spec import TabularSpec, TabularSpecResult


@dataclass(frozen=True)
class XYScatter(TabularSpec):
    """A column spec that renders a table as an XY scatter when called.

    Build one with :func:`xy_scatter`, which documents the options.
    """

    chart_name: ClassVar[str] = "xy_scatter"

    x: Hashable | None = None
    y: Hashable | None = None
    color: Hashable | None = None
    vdims: tuple[Hashable, ...] = ()
    size: int = 7
    cmap: str = "viridis"
    marker: str = "circle"

    def build(self, df) -> hv.Points:
        x_col, y_col = self.axes(df, self.x, self.y)
        if self.color is not None:
            self.check(df, self.color, "color")
        value_cols = self.value_columns(df, self.vdims, self.color)

        plot_df, names = self.frame(df, [x_col, y_col, *value_cols])
        x_name, y_name = names[x_col], names[y_col]

        chart_opts: dict[str, Any] = {"size": self.size, "marker": self.marker}
        if self.color is not None:
            chart_opts.update(color=names[self.color], cmap=self.cmap, colorbar=True)

        return hv.Points(
            plot_df, kdims=[x_name, y_name], vdims=[names[col] for col in value_cols]
        ).opts(**self.element_opts(xlabel=x_name, ylabel=y_name, **chart_opts))


def xy_scatter(
    x: Hashable | None = None,
    y: Hashable | None = None,
    *,
    color: Hashable | None = None,
    vdims: Sequence[Hashable] | None = None,
    size: int = 7,
    cmap: str = "viridis",
    marker: str = "circle",
    data_aspect: float | None = None,
    hover: bool = True,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    **opts: Any,
) -> XYScatter:
    """Build a container callback that scatters two columns of a table.

    The result takes the stored object alone, which is exactly what
    ``ResultDataSet(container=...)`` and ``ds_to_container`` hand it, so one spec
    works declaratively and through :class:`XYScatterResult`.

    Args:
        x: Column label for the x axis, as the frame holds it (a string for most
            frames, but an integer or timestamp label works too). Inferred from the
            numeric columns when omitted.
        y: Column label for the y axis. Inferred from the numeric columns when omitted.
        color: Column to colour points by (adds a colourbar).
        vdims: Extra columns to carry into the plot, so hover can show them.
        size: Point size.
        cmap: Colourmap used when *color* is set.
        marker: Point marker.
        data_aspect: Set to 1 to force equal x/y scaling — the honest choice for a
            cloud of positions, where an auto-scaled aspect makes an elongated cloud
            look round. Left unset otherwise, so a plot of unrelated quantities is
            not forced square.
        hover: Enable the hover tool.
        title: Plot title.
        xlabel: X axis label. Defaults to the column name.
        ylabel: Y axis label. Defaults to the column name.
        **opts: Passed through to ``hv.Points.opts``, so anything holoviews accepts
            (``alpha``, ``line_color``, ``width``, ...) works without a wrapper.

    Returns:
        An :class:`XYScatter` mapping the stored object to an ``hv.Points`` element.

    Raises:
        ValueError: at call time, if a named column is absent or x/y cannot be inferred.
        TypeError: at call time, if the stored object is not a table.
    """
    return XYScatter(
        x=x,
        y=y,
        color=color,
        vdims=tuple(vdims or ()),
        size=size,
        cmap=cmap,
        marker=marker,
        data_aspect=data_aspect,
        hover=hover,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        opts=dict(opts),
    )


class XYScatterResult(TabularSpecResult):
    """Renders every ``ResultDataSet`` sample as an XY scatter of two of its columns."""

    def to_plot(
        self,
        result_var: Parameter | None = None,
        x: Hashable | None = None,
        y: Hashable | None = None,
        *,
        color: Hashable | None = None,
        vdims: Sequence[Hashable] | None = None,
        size: int = 7,
        cmap: str = "viridis",
        marker: str = "circle",
        data_aspect: float | None = None,
        hover: bool = True,
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
        opts: dict[str, Any] | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        subsampling_divisions: int | None = None,
        **kwargs: Any,
    ) -> pn.panel | None:
        """Scatter columns *x* against *y* for each tabular result sample.

        The scatter options are named rather than swept up into ``**kwargs``, because
        ``**kwargs`` belongs to ``map_plot_panes``: every render path adds keywords of
        its own (``to()`` always passes ``override``/``agg_over_dims``/``agg_fn``,
        ``to_auto`` adds the plot-size and ``pane_layout`` keywords), and those must
        not end up in ``hv.Points.opts``. Naming the scatter options is what keeps the
        two sets apart; :func:`xy_scatter` documents what each one does.

        Args:
            result_var: Restrict to one result variable. Defaults to every
                ``ResultDataSet`` in the sweep.
            x: Column on the x axis (see :func:`xy_scatter` for x/y inference and
                every option from *color* to *ylabel*, which are passed straight on).
            y: Column on the y axis.
            color: Column to colour points by.
            vdims: Extra columns to carry into the plot for hover.
            size: Point size.
            cmap: Colourmap used when *color* is set.
            marker: Point marker.
            data_aspect: Set to 1 to force equal x/y scaling.
            hover: Enable the hover tool.
            title: Plot title.
            xlabel: X axis label.
            ylabel: Y axis label.
            opts: Extra ``hv.Points.opts`` keywords.
            hv_dataset: Pre-built dataset to render instead of this result's own.
            target_dimension: Dimension depth to recurse the panes down to.
            subsampling_divisions: Level to subsample the dataset at.
            **kwargs: Forwarded to ``map_plot_panes`` (layout and the plot-size
                keywords every ``to_auto`` render call carries).

        Returns:
            A panel of scatter plots, or None when the sweep has no tabular result.
        """
        return self.render_spec(
            xy_scatter(
                x=x,
                y=y,
                color=color,
                vdims=vdims,
                size=size,
                cmap=cmap,
                marker=marker,
                data_aspect=data_aspect,
                hover=hover,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                **(opts or {}),
            ),
            result_var=result_var,
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            subsampling_divisions=subsampling_divisions,
            **kwargs,
        )
