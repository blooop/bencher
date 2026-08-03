"""Opt-in helpers for renderers that interpret stored data as a table.

``ResultDataSet`` is an arbitrary per-sample data store; it has no tabular
contract. A :class:`TabularSpec` is one possible renderer for that data. It
coerces supported table-like payloads to a DataFrame, validates columns, and
builds a HoloViews element. Other renderers can interpret the same generic store
without depending on this module.

A spec is a frozen dataclass rather than a closure because a renderer declared
on a result variable is part of ``BenchCfg`` and must survive the result cache
and collect/render split.
"""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar

import holoviews as hv
import pandas as pd
import xarray as xr


def promote_named_index(df: pd.DataFrame) -> pd.DataFrame:
    """Move any *named* index level into a column, so it can be plotted.

    ``xr.Dataset.to_pandas()`` puts the dimension coordinate in the index and only
    the data variables in the columns, so a ``ResultDataSet`` built the idiomatic
    way from xarray holds its x axis there and no chart could reach it. An ordinary
    frame has an unnamed ``RangeIndex``, which is row position rather than data, and
    is left alone — as is a level whose name is already a column, since promoting it
    would collide.

    Promoted levels land at the front of the frame, which is also what column
    inference wants: for a one-variable timeseries the x axis comes first.

    A level whose name is already a column cannot be promoted — it would collide —
    and cannot be left named either: pandas rejects any lookup of a label that is
    both an index level and a column as ambiguous, so ``sort_values`` on it would
    raise. The column is what a chart asked for, so the level keeps its values and
    loses its name.
    """
    named = [name for name in df.index.names if name is not None]
    if not named:
        return df
    promote = [name for name in named if name not in df.columns]
    shadowed = {name for name in named if name in df.columns}
    # Shallow copy so rebinding the index below cannot reach the stored sample,
    # which is rendered again on every report build.
    out = df.reset_index(level=promote) if promote else df.copy(deep=False)
    if shadowed:
        # set_names, not rename: rename() takes a list as a *single* name for a
        # flat index. It returns a new Index, which matters because the shallow
        # copy above still shares the original's index object.
        out.index = out.index.set_names([None if n in shadowed else n for n in out.index.names])
    return out


def to_dataframe(obj: Any, chart: str) -> pd.DataFrame:
    """Coerce a stored payload to a DataFrame with plottable columns."""
    if isinstance(obj, pd.DataFrame):
        return promote_named_index(obj)
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


def resolve_columns(
    df: pd.DataFrame, columns: Hashable | Sequence[Hashable] | None, role: str, chart: str
) -> list[Hashable]:
    """The one-or-more columns a single-axis chart plots, inferred when omitted.

    A bare label is accepted as a single column, so the common case reads as
    ``column="dx_mm"`` rather than ``column=["dx_mm"]``. Inference takes *every*
    numeric column, which is the useful default for a frame holding only the
    measurement — name the columns whenever the frame carries anything else.
    """
    if columns is None:
        numeric = list(df.select_dtypes("number").columns)
        if not numeric:
            raise ValueError(
                f"{chart} needs at least one numeric column to plot, found none; "
                f"pass {role}= explicitly"
            )
        return numeric
    declared = list(columns) if isinstance(columns, (list, tuple)) else [columns]
    if not declared:
        raise ValueError(f"{chart} {role}= is empty; name at least one column")
    return [check_column(df, col, role, chart) for col in declared]


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

        The shared fields win over *chart_opts* for the keys they own, so a chart
        must not pass ``title``, ``data_aspect`` or ``tools`` as a chart option:
        the first two are only overridden when the field is set, but ``tools`` is
        always written (see below) and a chart option would be dropped silently.
        Pass such a value through ``opts`` instead, which is applied last.
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

    def columns(self, df: pd.DataFrame, columns: Hashable | Sequence[Hashable] | None, role: str):
        """The one-or-more columns for this chart (see :func:`resolve_columns`)."""
        return resolve_columns(df, columns, role, self.chart_name)

    def frame(self, df: pd.DataFrame, columns: Sequence[Hashable]):
        """The plotted columns with string dimension names (see :func:`plot_frame`)."""
        return plot_frame(df, columns, self.chart_name)

    def value_columns(
        self, df: pd.DataFrame, vdims: Sequence[Hashable], *extra: Hashable | None
    ) -> list[Hashable]:
        """The validated value dimensions: *vdims* plus any *extra* not already in them.

        *extra* is for columns a chart option implies (the one it colours by, say),
        which have to be carried as value dimensions to be usable by the plot but
        must not be listed twice. Every column returned is checked against *df*,
        including *extra*, so a chart that names one gets this module's
        available-columns message rather than a bare pandas ``KeyError`` from
        :meth:`frame`. ``None`` entries in *extra* are skipped, so an unset option
        needs no guard at the call site.
        """
        value_cols = list(vdims)
        for col in value_cols:
            self.check(df, col, "vdims entry")
        for col in extra:
            if col is None:
                continue
            self.check(df, col, "value column")
            if col not in value_cols:
                value_cols.append(col)
        return value_cols


__all__ = [
    "TabularSpec",
    "check_column",
    "plot_frame",
    "promote_named_index",
    "resolve_axes",
    "resolve_columns",
    "to_dataframe",
]
