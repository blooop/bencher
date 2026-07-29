"""Shared machinery for chart types that plot *inside* one tabular sample.

Every other chart in bencher plots across the sweep: an input variable on x, a
result variable on y, one point per sample. The charts built on this module plot
inside a single sample — a :class:`~bencher.variables.results.ResultDataSet` whose
rows are the measurement (landing points, a collected timeseries, a phase-space
cloud) — where the axes are columns the benchmark measured and the sweep
dimensions are what separate one plot from the next.

Each such chart is two objects with one implementation:

* a :class:`TabularSpec` subclass, built by a small factory function, which is a
  callable taking the stored object and returning a holoviews element. That makes
  it usable directly as a declared renderer, so the plot appears in
  ``result_vars`` order with the other results::

      series = bn.ResultDataSet(container=bn.xy_curve(x="time", y="signal"))

* a :class:`TabularSpecResult` subclass, so the same spec can be asked for as a
  report-level chart type::

      bench.add(bn.XYCurveResult, x="time", y="signal")

This module holds the parts that do not depend on which chart it is: coercing the
stored object to a DataFrame, validating and inferring columns, converting labels
at the holoviews boundary, and mapping a spec over every tabular sample.

A spec is a frozen dataclass rather than a closure because it has to survive
pickling: a result var declaring ``container=`` is part of ``BenchCfg``, which
goes into the result cache and through the collect/render split, and a local
function cannot be pickled.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Any, ClassVar

import holoviews as hv
import pandas as pd
import panel as pn
import xarray as xr
from param import Parameter

from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.variables.results import ResultDataSet


def to_dataframe(obj: Any, chart: str) -> pd.DataFrame:
    """Coerce a stored dataset object to a DataFrame with plottable columns."""
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, (xr.Dataset, xr.DataArray)):
        # reset_index so dimension coordinates become columns and can be plotted.
        return obj.to_dataframe().reset_index()
    if isinstance(obj, hv.Dataset):
        return obj.dframe()
    raise TypeError(
        f"{chart} needs a DataFrame, xarray Dataset/DataArray or hv.Dataset, "
        f"got {type(obj).__name__}"
    )


def check_column(df: pd.DataFrame, name: Hashable, role: str, chart: str) -> Hashable:
    if name not in df.columns:
        raise ValueError(
            f"{chart} {role}={name!r} is not a column of the result; "
            f"available columns: {list(df.columns)}"
        )
    return name


def resolve_axes(
    df: pd.DataFrame, x: Hashable | None, y: Hashable | None, chart: str
) -> tuple[Hashable, Hashable]:
    """The x and y columns, inferring unspecified ones from the numeric columns.

    Inference takes the first two numeric columns in frame order, which is only
    meaningful for a frame that holds exactly the pair being plotted — name the
    columns whenever the frame carries anything else (an index, a z coordinate).

    Labels come back exactly as the frame holds them: a column label is only a
    string by convention, and an xarray-derived frame can hand back integers or
    timestamps, which must still be usable to look the column back up.
    """
    if x is not None and y is not None:
        return check_column(df, x, "x", chart), check_column(df, y, "y", chart)
    numeric = list(df.select_dtypes("number").columns)
    if len(numeric) < 2:
        raise ValueError(
            f"{chart} needs two numeric columns to infer x and y, found "
            f"{numeric}; pass x= and y= explicitly"
        )
    if x is None and y is None:
        return numeric[0], numeric[1]
    if x is None:
        x_inferred = next((c for c in numeric if c != y), None)
        if x_inferred is None:
            raise ValueError(f"{chart} found no numeric column for x besides {y!r}")
        return x_inferred, check_column(df, y, "y", chart)
    y_inferred = next((c for c in numeric if c != x), None)
    if y_inferred is None:
        raise ValueError(f"{chart} found no numeric column for y besides {x!r}")
    return check_column(df, x, "x", chart), y_inferred


def plot_frame(
    df: pd.DataFrame, columns: Sequence[Hashable], chart: str
) -> tuple[pd.DataFrame, dict[Hashable, str]]:
    """The plotted columns alone, renamed so every dimension name is a string.

    A holoviews ``Dimension`` name has to be a string, but a column label does not,
    so every lookup above works with the frame's own labels and the conversion
    happens here, at the holoviews boundary, on a copy of the columns being plotted.

    Returns the frame to plot and the label -> dimension name mapping.
    """
    # dict keys dedupe (x may also be a vdim) while keeping the requested order.
    names = {col: str(col) for col in columns}
    if len(set(names.values())) != len(names):
        raise ValueError(
            f"{chart} cannot plot columns whose labels collide once converted to "
            f"strings: {sorted(names.values())}"
        )
    plot_df = df[list(names)]
    if any(col != name for col, name in names.items()):
        plot_df = plot_df.rename(columns=names)
    return plot_df, names


@dataclass(frozen=True)
class TabularSpec:
    """Base for a picklable spec that renders one sample's table as an element.

    Subclasses add the columns and per-chart options they need and implement
    :meth:`build`; the fields here are the ones every chart accepts. Build one with
    the chart's factory function rather than constructing it directly — the
    factory documents the options and is where the keyword-only boundary is.

    Fields are declared with defaults so a subclass can add its own, which means
    they land *before* the subclass's in the generated ``__init__``; the factory
    functions pass everything by keyword, so that ordering is never visible.
    """

    # Named on the class rather than passed around so error messages say which
    # chart rejected a column, without every helper call repeating the name.
    chart_name: ClassVar[str] = "tabular chart"

    title: str | None = None
    xlabel: str | None = None
    ylabel: str | None = None
    hover: bool = True
    data_aspect: float | None = None
    # Read-only by contract: the frozen dataclass cannot rebind it and nothing here
    # mutates it, so the shallow copy the factory takes is never written to.
    opts: Mapping[str, Any] = field(default_factory=dict)

    def __call__(self, obj: Any) -> Any:
        """Render *obj*, which is the stored object alone.

        This is the whole contract a ``ResultDataSet`` container has to satisfy, so
        a spec can be declared on a result var, attached to a single sample, or
        handed to a chart type, and the same code runs in all three cases.
        """
        return self.build(to_dataframe(obj, self.chart_name))

    def build(self, df: pd.DataFrame) -> Any:
        """Turn one sample's table into something panel can display."""
        raise NotImplementedError

    def element_opts(
        self, xlabel: str | None = None, ylabel: str | None = None, **chart_opts: Any
    ) -> dict[str, Any]:
        """The options to apply to the built element.

        *xlabel* and *ylabel* are the defaults to use when the spec does not
        override them — normally the plotted column names. *chart_opts* are the
        per-chart options; the spec's own ``opts`` are applied last, so anything
        holoviews accepts can be passed through the factory without a wrapper.
        """
        opts: dict[str, Any] = {}
        if (label := self.xlabel if self.xlabel is not None else xlabel) is not None:
            opts["xlabel"] = label
        if (label := self.ylabel if self.ylabel is not None else ylabel) is not None:
            opts["ylabel"] = label
        opts.update(chart_opts)
        if self.data_aspect is not None:
            opts["data_aspect"] = self.data_aspect
        # Set explicitly in both directions rather than omitted when off:
        # set_default_opts registers tools=["hover"] as a global default for most
        # element types, so leaving the key out would put hover back and make
        # hover=False a silent no-op.
        opts["tools"] = ["hover"] if self.hover else []
        if self.title is not None:
            opts["title"] = self.title
        opts.update(self.opts)
        return opts

    def check(self, df: pd.DataFrame, name: Hashable, role: str) -> Hashable:
        """Validate that *name* is a column of *df*, naming this chart on failure."""
        return check_column(df, name, role, self.chart_name)

    def axes(self, df: pd.DataFrame, x: Hashable | None, y: Hashable | None):
        """The x and y columns for this chart (see :func:`resolve_axes`)."""
        return resolve_axes(df, x, y, self.chart_name)

    def frame(self, df: pd.DataFrame, columns: Sequence[Hashable]):
        """The plotted columns with string dimension names (see :func:`plot_frame`)."""
        return plot_frame(df, columns, self.chart_name)

    def value_columns(
        self, df: pd.DataFrame, vdims: Sequence[Hashable], *extra: Hashable | None
    ) -> list[Hashable]:
        """The validated value dimensions: *vdims* plus any *extra* not already in them.

        *extra* is for columns a chart option implies (the one it colours by, say),
        which have to be carried as value dimensions to be usable by the plot but
        must not be listed twice.
        """
        value_cols = list(vdims)
        for col in value_cols:
            self.check(df, col, "vdims entry")
        for col in extra:
            if col is not None and col not in value_cols:
                value_cols.append(col)
        return value_cols


class TabularSpecResult(HoloviewResult):
    """Base for chart types that render each tabular sample through a spec.

    One plot per sample rather than one plot for the sweep: the rows of a sample
    are the measurement, so averaging them across samples would destroy the thing
    being measured. Non-tabular results are skipped — a chart of a sample's columns
    is only defined for a tabular result.

    Subclasses implement ``to_plot``, naming their spec options explicitly and
    handing the built spec to :meth:`render_spec`.
    """

    def render_spec(
        self,
        spec: TabularSpec,
        result_var: Parameter | None = None,
        hv_dataset=None,
        target_dimension: int = 0,
        subsampling_divisions: int | None = None,
        **kwargs: Any,
    ) -> pn.panel | None:
        """Map *spec* over every tabular sample and lay the results out.

        Args:
            spec: The chart spec to render each sample through.
            result_var: Restrict to one result variable. Defaults to every
                ``ResultDataSet`` in the sweep.
            hv_dataset: Pre-built dataset to render instead of this result's own.
            target_dimension: Dimension depth to recurse the panes down to.
            subsampling_divisions: Level to subsample the dataset at.
            **kwargs: Forwarded to ``map_plot_panes`` (layout and the plot-size
                keywords every ``to_auto`` render call carries).

        Returns:
            A panel of plots, or None when the sweep has no tabular result.
        """
        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(
                ReduceType.SQUEEZE, subsampling_divisions=subsampling_divisions
            )
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)
        return self.map_plot_panes(
            partial(self.ds_to_container, container=spec),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultDataSet,),
            **kwargs,
        )


__all__ = [
    "TabularSpec",
    "TabularSpecResult",
    "check_column",
    "plot_frame",
    "resolve_axes",
    "to_dataframe",
]
