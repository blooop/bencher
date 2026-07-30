"""Plot one or more *measured* columns of a tabular result against an x column.

Where ``xy_scatter`` draws an unordered cloud, this draws a connected series: the
common case is a benchmark that collects a signal over time and stores the whole
trace as one sample, so the rows are a curve and the sweep dimensions separate one
trace from the next. ``CurveResult`` and ``LineResult`` plot *across* the sweep and
cannot show this — they have one value per sample, not a series inside it.

The same spec covers a trajectory: ``sort=False`` keeps the frame's row order, so a
path that doubles back in x (a robot's motion, a phase-space orbit) is drawn as
travelled rather than sorted into a function of x.

Two ways in, same renderer:

* declaratively, so the trace renders with the other results in ``result_vars``
  order::

      trace = bn.ResultDataSet(container=bn.xy_curve(x="time", y="signal"))

* explicitly, for a report-level plot::

      bench.add(bn.XYCurveResult, x="time", y=["signal", "reference"])
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import holoviews as hv
import panel as pn
from param import Parameter

from bencher.results.dataset_result import render_data_samples
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.holoview_results.tabular_spec import TabularSpec


@dataclass(frozen=True)
class XYCurve(TabularSpec):
    """A column spec that renders a table as one or more curves when called.

    Build one with :func:`xy_curve`, which documents the options.
    """

    chart_name: ClassVar[str] = "xy_curve"

    x: Hashable | None = None
    # A tuple rather than a list so the dataclass stays hashable and comparable;
    # the factory does the conversion, and a bare column label is accepted there.
    y: Hashable | tuple[Hashable, ...] | None = None
    vdims: tuple[Hashable, ...] = ()
    sort: bool = True
    markers: bool = False
    size: int = 5

    def _resolve_columns(self, df) -> tuple[Hashable, list[Hashable]]:
        """The x column and the list of y columns, inferring whichever is omitted.

        Only one of the two inference paths runs: with no y at all the pairwise
        inference resolves both axes, so a two-column frame needs no arguments; with
        y named, x is inferred against the first of them.
        """
        if self.y is None:
            x_col, y_col = self.axes(df, self.x, None)
            return x_col, [y_col]
        declared = list(self.y) if isinstance(self.y, tuple) else [self.y]
        if not declared:
            raise ValueError(f"{self.chart_name} y= is empty; name at least one column")
        y_cols = [self.check(df, col, "y") for col in declared]
        if self.x is None:
            return self.axes(df, None, y_cols[0])[0], y_cols
        return self.check(df, self.x, "x"), y_cols

    def build(self, df) -> hv.Overlay:
        x_col, y_cols = self._resolve_columns(df)
        value_cols = self.value_columns(df, self.vdims, *y_cols)

        plot_df, names = self.frame(df, [x_col, *value_cols])
        x_name = names[x_col]
        if self.sort:
            # A curve connects rows in order, so unsorted x zigzags back over
            # itself. Sorting is what makes it a function of x; sort=False is the
            # opt-out for a trajectory, where row order *is* the data.
            plot_df = plot_df.sort_values(x_name, kind="stable")

        # ylabel is left to holoviews for an overlay of several series, where no
        # single column name is the right label.
        single = len(y_cols) == 1
        opts = self.element_opts(xlabel=x_name, ylabel=names[y_cols[0]] if single else None)

        overlay = hv.Overlay()
        for col in y_cols:
            name = names[col]
            # The series column first — that is the y axis — then the requested
            # extras, which holoviews carries along for hover without plotting them.
            vdims = [name, *(names[c] for c in self.vdims if c != col)]
            overlay *= hv.Curve(plot_df, kdims=[x_name], vdims=vdims, label=name).opts(**opts)
            if self.markers:
                # Unlabelled and legend-suppressed: the markers annotate the curve
                # they sit on rather than being a series of their own, so a legend
                # entry here would double every name.
                overlay *= hv.Scatter(plot_df, kdims=[x_name], vdims=vdims).opts(
                    size=self.size, show_legend=False, **opts
                )
        # legend_position is an Overlay option, not a Curve one, so it goes here
        # rather than through element_opts.
        return overlay if single else overlay.opts(legend_position="right")


def xy_curve(
    x: Hashable | None = None,
    y: Hashable | Sequence[Hashable] | None = None,
    *,
    vdims: Sequence[Hashable] | None = None,
    sort: bool = True,
    markers: bool = False,
    size: int = 5,
    data_aspect: float | None = None,
    hover: bool = True,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    **opts: Any,
) -> XYCurve:
    """Build a container callback that draws columns of a table as curves.

    The result takes the stored object alone, which is exactly what
    ``ResultDataSet(container=...)`` and ``ds_to_container`` hand it, so one spec
    works declaratively and through :class:`XYCurveResult`.

    Args:
        x: Column label for the x axis, as the frame holds it. Inferred from the
            numeric columns when omitted. A frame produced by ``.to_pandas()`` keeps
            its dimension coordinate in the index; that index is promoted to a
            column, so ``x="time"`` works on one.
        y: Column label for the y axis, or a sequence of labels to overlay several
            series with a legend. Inferred from the numeric columns when omitted.
        vdims: Extra columns to carry into the plot, so hover can show them.
        sort: Sort rows by *x* before connecting them, which is what makes the
            result a function of x. Pass False for a trajectory that doubles back,
            where the frame's row order is the data.
        markers: Overlay a marker per row, so individual samples are visible on a
            sparse series.
        size: Marker size, when *markers* is set.
        data_aspect: Forces the x/y scale ratio. Left unset by default, so a plot of
            unrelated quantities is not forced square.
        hover: Enable the hover tool.
        title: Plot title.
        xlabel: X axis label. Defaults to the column name.
        ylabel: Y axis label. Defaults to the column name for a single series, and is
            left to holoviews for several.
        **opts: Passed through to the element's ``.opts``, so anything holoviews
            accepts (``color``, ``line_width``, ``alpha``, ...) works without a
            wrapper.

    Returns:
        An :class:`XYCurve` mapping the stored object to an ``hv.Overlay`` of curves.

    Raises:
        ValueError: at call time, if a named column is absent or x/y cannot be inferred.
        TypeError: at call time, if the stored object is not a table.
    """
    return XYCurve(
        x=x,
        y=tuple(y) if isinstance(y, (list, tuple)) else y,
        vdims=tuple(vdims or ()),
        sort=sort,
        markers=markers,
        size=size,
        data_aspect=data_aspect,
        hover=hover,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        opts=dict(opts),
    )


class XYCurveResult(HoloviewResult):
    """Renders every ``ResultDataSet`` sample as curves over one of its columns.

    One plot per sample rather than one plot for the sweep: the rows of a sample are
    the series, so averaging them across samples would destroy the thing being
    measured. Other result types are skipped — a curve over a column is only defined
    for a tabular result.
    """

    def to_plot(
        self,
        result_var: Parameter | None = None,
        x: Hashable | None = None,
        y: Hashable | Sequence[Hashable] | None = None,
        *,
        vdims: Sequence[Hashable] | None = None,
        sort: bool = True,
        markers: bool = False,
        size: int = 5,
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
        """Draw columns *y* against *x* for each tabular result sample.

        The curve options are named rather than swept up into ``**kwargs``, because
        ``**kwargs`` belongs to ``map_plot_panes``: every render path adds keywords of
        its own (``to()`` always passes ``override``/``agg_over_dims``/``agg_fn``,
        ``to_auto`` adds the plot-size and ``pane_layout`` keywords), and those must
        not end up in the element's opts. Naming the curve options is what keeps the
        two sets apart; :func:`xy_curve` documents what each one does.

        Args:
            result_var: Restrict to one result variable. Defaults to every
                ``ResultDataSet`` in the sweep.
            x: Column on the x axis (see :func:`xy_curve` for inference and every
                option from *vdims* to *ylabel*, which are passed straight on).
            y: Column, or sequence of columns, to draw against *x*.
            vdims: Extra columns to carry into the plot for hover.
            sort: Sort rows by *x*; pass False for a trajectory.
            markers: Overlay a marker per row.
            size: Marker size, when *markers* is set.
            data_aspect: Forces the x/y scale ratio.
            hover: Enable the hover tool.
            title: Plot title.
            xlabel: X axis label.
            ylabel: Y axis label.
            opts: Extra element ``.opts`` keywords.
            hv_dataset: Pre-built dataset to render instead of this result's own.
            target_dimension: Dimension depth to recurse the panes down to.
            subsampling_divisions: Level to subsample the dataset at.
            **kwargs: Forwarded to ``map_plot_panes`` (layout and the plot-size
                keywords every ``to_auto`` render call carries).

        Returns:
            A panel of curve plots, or None when the sweep has no tabular result.
        """
        return render_data_samples(
            self,
            renderer=xy_curve(
                x=x,
                y=y,
                vdims=vdims,
                sort=sort,
                markers=markers,
                size=size,
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
