"""Bin one or more *measured* columns of a tabular result into a histogram.

``HistogramResult`` bins a ``ResultFloat`` across the sweep: the values it counts are
one per sample, so what it shows is the spread of the repeats. This bins inside a
single sample — a ``ResultDataSet`` whose rows are the measurement — so what it shows
is the distribution the sample itself measured, and the sweep dimensions separate one
distribution from the next.

Two ways in, same renderer:

* declaratively, so the distribution renders with the other results in
  ``result_vars`` order::

      errors = bn.ResultDataSet(container=bn.xy_histogram("error_mm", bins=30))

* explicitly, for a report-level plot::

      bench.add(bn.XYHistogramResult, column=["error_mm", "baseline_mm"])
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

import holoviews as hv
import numpy as np
import panel as pn
from param import Parameter

from bencher.results.dataset_result import render_data_samples
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.results.holoview_results.tabular_spec import TabularSpec

# Enough transparency that an overlaid distribution is still readable underneath.
# Only applied when there is more than one, and `**opts` still overrides it.
_OVERLAY_ALPHA = 0.55


@dataclass(frozen=True)
class XYHistogram(TabularSpec):
    """A column spec that renders a table as one or more histograms when called.

    Build one with :func:`xy_histogram`, which documents the options.
    """

    chart_name: ClassVar[str] = "xy_histogram"

    column: Hashable | tuple[Hashable, ...] | None = None
    bins: int = 20
    bin_range: tuple[float, float] | None = None
    density: bool = False

    def build(self, df) -> hv.Overlay:
        cols = self.columns(df, self.column, "column")
        plot_df, names = self.frame(df, cols)

        # One shared bin range across the overlay, so two distributions drawn
        # together are actually comparable rather than each binned to its own span.
        bin_range = self.bin_range
        if bin_range is None and len(cols) > 1:
            values = plot_df.to_numpy(dtype=float, na_value=np.nan)
            if np.isfinite(values).any():
                bin_range = (float(np.nanmin(values)), float(np.nanmax(values)))

        single = len(cols) == 1
        y_name = "density" if self.density else "count"
        opts = self.element_opts(
            xlabel=names[cols[0]] if single else None,
            ylabel=y_name,
            **({} if single else {"alpha": _OVERLAY_ALPHA}),
        )

        overlay = hv.Overlay()
        for col in cols:
            name = names[col]
            counts, edges = self._counts(plot_df[name].to_numpy(dtype=float), bin_range)
            overlay *= hv.Histogram(
                (edges, counts), kdims=[name if single else "value"], vdims=[y_name], label=name
            ).opts(**opts)
        # legend_position is an Overlay option, not a Histogram one.
        return overlay if single else overlay.opts(legend_position="right")

    def _counts(self, values, bin_range) -> tuple[Any, Any]:
        """Bin *values*, tolerating a column that is empty or all-NaN.

        numpy cannot pick a range for an empty array and raises; a run that measured
        nothing should be an empty plot, so the bins are produced anyway and left at
        zero. NaN is how bencher marks a sample missing, so it is dropped rather than
        poisoning the whole range.
        """
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            # Unpacked rather than star-splatted: numpy's overloads cannot see that the
            # splatted tuple has exactly two elements, and naming the ends reads better.
            low, high = bin_range or (0.0, 1.0)
            edges = np.linspace(low, high, self.bins + 1)
            return np.zeros(self.bins), edges
        return np.histogram(finite, bins=self.bins, range=bin_range, density=self.density)


def xy_histogram(
    column: Hashable | Sequence[Hashable] | None = None,
    *,
    bins: int = 20,
    bin_range: tuple[float, float] | None = None,
    density: bool = False,
    hover: bool = True,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    data_aspect: float | None = None,
    **opts: Any,
) -> XYHistogram:
    """Build a container callback that bins columns of a table into histograms.

    The result takes the stored object alone, which is exactly what
    ``ResultDataSet(container=...)`` and ``ds_to_container`` hand it, so one spec
    works declaratively and through :class:`XYHistogramResult`.

    Args:
        column: Column label to bin, or a sequence of labels to overlay several
            distributions with a legend. Defaults to every numeric column, which is
            what a frame holding only the measurement wants.
        bins: Number of bins.
        bin_range: ``(low, high)`` to bin over. Defaults to the data's own span for a
            single column, and to the span across all of them for an overlay, so two
            distributions drawn together are comparable.
        density: Normalise to a probability density instead of counting rows.
        hover: Enable the hover tool.
        title: Plot title.
        xlabel: X axis label. Defaults to the column name for a single distribution,
            and is left to holoviews for several.
        ylabel: Y axis label. Defaults to ``"count"``, or ``"density"``.
        data_aspect: Forces the x/y scale ratio. Left unset by default.
        **opts: Passed through to ``hv.Histogram.opts``, so anything holoviews accepts
            (``alpha``, ``color``, ``line_color``, ...) works without a wrapper.

    Returns:
        An :class:`XYHistogram` mapping the stored object to an ``hv.Overlay``.

    Raises:
        ValueError: at call time, if a named column is absent or none can be inferred.
        TypeError: at call time, if the stored object is not a table.
    """
    return XYHistogram(
        column=tuple(column) if isinstance(column, (list, tuple)) else column,
        bins=bins,
        bin_range=bin_range,
        density=density,
        hover=hover,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        data_aspect=data_aspect,
        opts=dict(opts),
    )


class XYHistogramResult(HoloviewResult):
    """Renders every ``ResultDataSet`` sample as a histogram of its own rows.

    One plot per sample rather than one plot for the sweep: the rows of a sample are
    the distribution, so pooling them across samples would destroy the thing being
    measured. Other result types are skipped — binning a column is only defined for a
    tabular result.
    """

    def to_plot(
        self,
        result_var: Parameter | None = None,
        column: Hashable | Sequence[Hashable] | None = None,
        *,
        bins: int = 20,
        bin_range: tuple[float, float] | None = None,
        density: bool = False,
        hover: bool = True,
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None,
        data_aspect: float | None = None,
        opts: dict[str, Any] | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        subsampling_divisions: int | None = None,
        **kwargs: Any,
    ) -> pn.panel | None:
        """Bin *column* for each tabular result sample.

        The histogram options are named rather than swept up into ``**kwargs``,
        because ``**kwargs`` belongs to ``map_plot_panes``: every render path adds
        keywords of its own (``to()`` always passes
        ``override``/``agg_over_dims``/``agg_fn``, ``to_auto`` adds the plot-size and
        ``pane_layout`` keywords), and those must not end up in the element's opts.
        :func:`xy_histogram` documents what each one does.

        Args:
            result_var: Restrict to one result variable. Defaults to every
                ``ResultDataSet`` in the sweep.
            column: Column, or sequence of columns, to bin (see :func:`xy_histogram`
                for inference and every option from *bins* to *data_aspect*, which
                are passed straight on).
            bins: Number of bins.
            bin_range: ``(low, high)`` to bin over.
            density: Normalise to a probability density.
            hover: Enable the hover tool.
            title: Plot title.
            xlabel: X axis label.
            ylabel: Y axis label.
            data_aspect: Forces the x/y scale ratio.
            opts: Extra ``hv.Histogram.opts`` keywords.
            hv_dataset: Pre-built dataset to render instead of this result's own.
            target_dimension: Dimension depth to recurse the panes down to.
            subsampling_divisions: Level to subsample the dataset at.
            **kwargs: Forwarded to ``map_plot_panes`` (layout and the plot-size
                keywords every ``to_auto`` render call carries).

        Returns:
            A panel of histograms, or None when the sweep has no tabular result.
        """
        return render_data_samples(
            self,
            renderer=xy_histogram(
                column=column,
                bins=bins,
                bin_range=bin_range,
                density=density,
                hover=hover,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                data_aspect=data_aspect,
                **(opts or {}),
            ),
            result_var=result_var,
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            subsampling_divisions=subsampling_divisions,
            **kwargs,
        )
