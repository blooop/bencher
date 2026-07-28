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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any

import holoviews as hv
import pandas as pd
import panel as pn
import xarray as xr
from param import Parameter

from bencher.results.bench_result_base import ReduceType
from bencher.results.holoview_results.holoview_result import HoloviewResult
from bencher.variables.results import ResultDataSet


def _to_dataframe(obj: Any) -> pd.DataFrame:
    """Coerce a stored dataset object to a DataFrame with plottable columns."""
    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, (xr.Dataset, xr.DataArray)):
        # reset_index so dimension coordinates become columns and can be plotted.
        return obj.to_dataframe().reset_index()
    if isinstance(obj, hv.Dataset):
        return obj.dframe()
    raise TypeError(
        f"xy_scatter needs a DataFrame, xarray Dataset/DataArray or hv.Dataset, "
        f"got {type(obj).__name__}"
    )


def _check_column(df: pd.DataFrame, name: str, role: str) -> str:
    if name not in df.columns:
        raise ValueError(
            f"xy_scatter {role}={name!r} is not a column of the result; "
            f"available columns: {list(df.columns)}"
        )
    return name


def _resolve_axes(df: pd.DataFrame, x: str | None, y: str | None) -> tuple[str, str]:
    """The x and y columns, inferring unspecified ones from the numeric columns.

    Inference takes the first two numeric columns in frame order, which is only
    meaningful for a frame that holds exactly the pair being plotted — name the
    columns whenever the frame carries anything else (an index, a z coordinate).
    """
    if x is not None and y is not None:
        return _check_column(df, x, "x"), _check_column(df, y, "y")
    numeric = [str(c) for c in df.select_dtypes("number").columns]
    if len(numeric) < 2:
        raise ValueError(
            "xy_scatter needs two numeric columns to infer x and y, found "
            f"{numeric}; pass x= and y= explicitly"
        )
    if x is None and y is None:
        return numeric[0], numeric[1]
    if x is None:
        x_inferred = next((c for c in numeric if c != y), None)
        if x_inferred is None:
            raise ValueError(f"xy_scatter found no numeric column for x besides {y!r}")
        return x_inferred, _check_column(df, y, "y")
    y_inferred = next((c for c in numeric if c != x), None)
    if y_inferred is None:
        raise ValueError(f"xy_scatter found no numeric column for y besides {x!r}")
    return _check_column(df, x, "x"), y_inferred


@dataclass(frozen=True)
class XYScatter:
    """A column spec that renders a table as an XY scatter when called.

    A class rather than a closure so it survives pickling: a result var declaring
    ``container=`` is part of ``BenchCfg``, which goes into the result cache and
    through the collect/render split, and a local function cannot be pickled. Build
    one with :func:`xy_scatter`.
    """

    x: str | None = None
    y: str | None = None
    color: str | None = None
    vdims: tuple[str, ...] = ()
    size: int = 7
    cmap: str = "viridis"
    marker: str = "circle"
    data_aspect: float | None = None
    hover: bool = True
    title: str | None = None
    xlabel: str | None = None
    ylabel: str | None = None
    opts: tuple[tuple[str, Any], ...] = ()

    def __call__(self, obj: Any) -> hv.Points:
        df = _to_dataframe(obj)
        x_col, y_col = _resolve_axes(df, self.x, self.y)
        value_dims = [str(c) for c in self.vdims]
        for name in value_dims:
            _check_column(df, name, "vdims entry")
        if self.color is not None:
            _check_column(df, self.color, "color")
            if self.color not in value_dims:
                value_dims.append(self.color)

        point_opts: dict[str, Any] = {
            "size": self.size,
            "marker": self.marker,
            "xlabel": self.xlabel if self.xlabel is not None else x_col,
            "ylabel": self.ylabel if self.ylabel is not None else y_col,
        }
        if self.color is not None:
            point_opts.update(color=self.color, cmap=self.cmap, colorbar=True)
        if self.data_aspect is not None:
            point_opts["data_aspect"] = self.data_aspect
        if self.hover:
            point_opts["tools"] = ["hover"]
        if self.title is not None:
            point_opts["title"] = self.title
        point_opts.update(self.opts)

        return hv.Points(df, kdims=[x_col, y_col], vdims=value_dims).opts(**point_opts)


def xy_scatter(
    x: str | None = None,
    y: str | None = None,
    *,
    color: str | None = None,
    vdims: Sequence[str] | None = None,
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
        x: Column on the x axis. Inferred from the numeric columns when omitted.
        y: Column on the y axis. Inferred from the numeric columns when omitted.
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
        vdims=tuple(str(v) for v in (vdims or ())),
        size=size,
        cmap=cmap,
        marker=marker,
        data_aspect=data_aspect,
        hover=hover,
        title=title,
        xlabel=xlabel,
        ylabel=ylabel,
        opts=tuple(opts.items()),
    )


class XYScatterResult(HoloviewResult):
    """Renders every ``ResultDataSet`` sample as an XY scatter of two of its columns.

    One plot per sample rather than one plot for the sweep: the rows of a sample are
    the cloud, so averaging them across samples would destroy the thing being
    measured. Other result types are skipped — a scatter of two columns is only
    defined for a tabular result.
    """

    def to_plot(
        self,
        result_var: Parameter | None = None,
        x: str | None = None,
        y: str | None = None,
        *,
        color: str | None = None,
        vdims: Sequence[str] | None = None,
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
        container = xy_scatter(
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
        )

        if hv_dataset is None:
            hv_dataset = self.to_hv_dataset(
                ReduceType.SQUEEZE, subsampling_divisions=subsampling_divisions
            )
        elif not isinstance(hv_dataset, hv.Dataset):
            hv_dataset = hv.Dataset(hv_dataset)
        return self.map_plot_panes(
            partial(self.ds_to_container, container=container),
            hv_dataset=hv_dataset,
            target_dimension=target_dimension,
            result_var=result_var,
            result_types=(ResultDataSet,),
            **kwargs,
        )
