"""Bin two *measured* columns of a tabular result into hexagonal tiles.

The density counterpart to ``xy_scatter``, and the reason to reach for it is
overplotting: a cloud of sixty points reads fine as points, but at tens of thousands
the markers saturate and the shape of the distribution — where the mass actually is —
is exactly what gets lost. Same axes, same options; the marks become counts.

Two ways in, same renderer:

* declaratively, so the density renders with the other results in ``result_vars``
  order::

      cloud = bn.ResultDataSet(container=bn.xy_hexbin(x="dx_mm", y="dy_mm"))

* explicitly, for a report-level plot::

      bench.add(bn.XYHexbinResult, x="dx_mm", y="dy_mm", gridsize=40)
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any, ClassVar

import holoviews as hv
import panel as pn
from param import Parameter

from bencher.results.dataset_result import render_data_samples
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.holoview_results.tabular_spec import TabularSpec


@dataclass(frozen=True)
class XYHexbin(TabularSpec):
    """A column spec that renders a table as hexagonally-binned density when called.

    Build one with :func:`xy_hexbin`, which documents the options.
    """

    chart_name: ClassVar[str] = "xy_hexbin"

    x: Hashable | None = None
    y: Hashable | None = None
    gridsize: int = 25
    cmap: str = "viridis"
    min_count: int | None = None
    colorbar: bool = True

    def build(self, df) -> hv.HexTiles:
        x_col, y_col = self.axes(df, self.x, self.y)
        plot_df, names = self.frame(df, [x_col, y_col])
        x_name, y_name = names[x_col], names[y_col]

        chart_opts: dict[str, Any] = {
            "gridsize": self.gridsize,
            "cmap": self.cmap,
            "colorbar": self.colorbar,
        }
        if self.min_count is not None:
            chart_opts["min_count"] = self.min_count

        return hv.HexTiles(plot_df, kdims=[x_name, y_name]).opts(
            **self.element_opts(xlabel=x_name, ylabel=y_name, **chart_opts)
        )


def xy_hexbin(
    x: Hashable | None = None,
    y: Hashable | None = None,
    *,
    gridsize: int = 25,
    cmap: str = "viridis",
    min_count: int | None = None,
    colorbar: bool = True,
    data_aspect: float | None = None,
    hover: bool = True,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    **opts: Any,
) -> XYHexbin:
    """Build a container callback that hex-bins two columns of a table.

    The result takes the stored object alone, which is exactly what
    ``ResultDataSet(container=...)`` and ``ds_to_container`` hand it, so one spec
    works declaratively and through :class:`XYHexbinResult`.

    Args:
        x: Column label for the x axis, as the frame holds it. Inferred from the
            numeric columns when omitted.
        y: Column label for the y axis. Inferred from the numeric columns when omitted.
        gridsize: Number of hexagons across the x axis. Raise it for a large cloud,
            lower it for a sparse one — too fine and every tile holds one point, which
            is a scatter with worse marks.
        cmap: Colourmap for the counts.
        min_count: Hide tiles with fewer than this many points. Set to 1 to drop empty
            tiles rather than drawing them at zero.
        colorbar: Show the count scale. On by default, since a density plot without one
            shows shape but no magnitude.
        data_aspect: Set to 1 to force equal x/y scaling — the honest choice for a
            cloud of positions, where an auto-scaled aspect makes an elongated cloud
            look round. Left unset otherwise.
        hover: Enable the hover tool.
        title: Plot title.
        xlabel: X axis label. Defaults to the column name.
        ylabel: Y axis label. Defaults to the column name.
        **opts: Passed through to ``hv.HexTiles.opts``, so anything holoviews accepts
            (``alpha``, ``line_color``, ``width``, ...) works without a wrapper.

    Returns:
        An :class:`XYHexbin` mapping the stored object to an ``hv.HexTiles`` element.

    Raises:
        ValueError: at call time, if a named column is absent or x/y cannot be inferred.
        TypeError: at call time, if the stored object is not a table.
    """
    return XYHexbin(
        x=x,
        y=y,
        gridsize=gridsize,
        cmap=cmap,
        min_count=min_count,
        colorbar=colorbar,
        data_aspect=data_aspect,
        hover=hover,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        opts=dict(opts),
    )


class XYHexbinResult(HoloviewResult):
    """Renders every ``ResultDataSet`` sample as a hex-binned density of two columns.

    One plot per sample rather than one plot for the sweep: the rows of a sample are
    the density, so pooling them across samples would destroy the thing being
    measured. Other result types are skipped — binning two columns is only defined for
    a tabular result.
    """

    def to_plot(
        self,
        result_var: Parameter | None = None,
        x: Hashable | None = None,
        y: Hashable | None = None,
        *,
        gridsize: int = 25,
        cmap: str = "viridis",
        min_count: int | None = None,
        colorbar: bool = True,
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
        """Hex-bin columns *x* against *y* for each tabular result sample.

        The hexbin options are named rather than swept up into ``**kwargs``, because
        ``**kwargs`` belongs to ``map_plot_panes``: every render path adds keywords of
        its own (``to()`` always passes ``override``/``agg_over_dims``/``agg_fn``,
        ``to_auto`` adds the plot-size and ``pane_layout`` keywords), and those must
        not end up in the element's opts. :func:`xy_hexbin` documents what each one
        does.

        Args:
            result_var: Restrict to one result variable. Defaults to every
                ``ResultDataSet`` in the sweep.
            x: Column on the x axis (see :func:`xy_hexbin` for x/y inference and every
                option from *gridsize* to *ylabel*, which are passed straight on).
            y: Column on the y axis.
            gridsize: Number of hexagons across the x axis.
            cmap: Colourmap for the counts.
            min_count: Hide tiles with fewer than this many points.
            colorbar: Show the count scale.
            data_aspect: Set to 1 to force equal x/y scaling.
            hover: Enable the hover tool.
            title: Plot title.
            xlabel: X axis label.
            ylabel: Y axis label.
            opts: Extra ``hv.HexTiles.opts`` keywords.
            hv_dataset: Pre-built dataset to render instead of this result's own.
            target_dimension: Dimension depth to recurse the panes down to.
            subsampling_divisions: Level to subsample the dataset at.
            **kwargs: Forwarded to ``map_plot_panes`` (layout and the plot-size
                keywords every ``to_auto`` render call carries).

        Returns:
            A panel of hexbin plots, or None when the sweep has no tabular result.
        """
        return render_data_samples(
            self,
            renderer=xy_hexbin(
                x=x,
                y=y,
                gridsize=gridsize,
                cmap=cmap,
                min_count=min_count,
                colorbar=colorbar,
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
