"""The ``svg`` plotting backend: charts as self-contained, optionally animated SVG.

``BenchRunCfg(backend="svg")`` swaps holoviews charts for matplotlib-drawn SVGs that
render anywhere an ``<img>`` does -- a GitHub PR description, an issue, a README --
because they carry no script, no font and no external reference.

The charts come in three kinds:

* value charts (``line``, ``curve``, ``heatmap``, ``bar``, ``scatter``): one value per
  sweep point, repeats reduced by mean (the curve shows the standard deviation as a
  band, like its holoviews twin);
* distribution charts (``box_whisker``, ``violin``, ``scatter_jitter``, ``histogram``,
  ``band``): every repeat drawn as a dot, with a thick median mark;
* the ``table`` of every sample, and the tabular charts (``xy_scatter``, ``xy_curve``,
  ``xy_histogram``, ``xy_hexbin``) that draw the table one ``ResultDataSet`` sample holds;
* the 3D charts: ``volume`` (filled contour slices) and ``surface`` (a fixed 3D view).

Each chart shows up to three dimensions (an x axis, a y axis for the heatmap, a colour
for the hue). Every other swept dimension, ``over_time`` included, is a *frame dim*: each
combination of their values is one frame. Up to MAX_SVG_PANELS frames are drawn as a grid
of small panels, all at once, sharing axes, colour scale, legend and title; a CSS
highlight walks the panels and stops for ``prefers-reduced-motion``. Past that (or with
``svg_layout="frames"``) the frames are stacked in one chart and switched with SMIL
``<animate calcMode="discrete">``, with a label naming the current values and a progress
bar. Either way, axes and colour limits are fixed across frames so frames compare by eye.
One frame is a static SVG. The band and the table show every dimension at once (the
band pools them into its percentiles), so they never animate; a tabular chart draws one
sample per frame.

Each chart declares the sweep shapes it draws as a ``PlotFilter``. A sweep outside them
selects the holoviews (or plotly) twin instead (see ``bencher/plugins/builtins.py``), and a matching
sweep with no result var the chart can draw hands over to that twin at render time, so
the backend swap never loses a plot.
"""

from __future__ import annotations

import contextvars
import dataclasses
import functools
import io
import itertools
import logging
import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from bencher.optional_deps import pn
from bencher.plotting.plot_filter import PlotFilter, VarRange
from bencher.results.bench_result_base import BenchResultBase
from bencher.utils import label_with_units
from bencher.variables.results import (
    SCALAR_RESULT_TYPES,
    ResultBool,
    ResultDataSet,
    ResultFloat,
    ResultString,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import ModuleType

    import pandas as pd
    import xarray as xr
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from bencher.plotting.plt_cnt_cfg import PltCntCfg
    from bencher.plugins.bench_data import BenchData
    from bencher.plugins.plugin import PlotPlugin

    # Loads one stored ResultDataSet cell: (cell value, result var) -> payload or None.
    SampleLoader = Callable[[Any, Any], Any]

log = logging.getLogger(__name__)

SVG_BACKEND = "svg"

# The most combinations of the unshown dims a chart draws, as frames or as a forced
# grid. A GitHub <img> has no controls, so every frame plays; past this many the
# animation is too long to read and the file too large to embed. The rest are dropped
# with a warning in the log and a note on the image.
MAX_SVG_FRAMES = 60
FRAME_SECONDS = 1.0
# Up to this many combinations of the dims a chart does not show are drawn as a grid of
# small panels, all visible at once; past it the panels get too small to read and the
# chart steps through them as frames instead (``svg_layout="auto"``).
MAX_SVG_PANELS = 12
SVG_LAYOUTS = ("auto", "grid", "frames")
# The highlight that walks the grid's panels: seconds per panel, the fade at each end,
# and how far the panels out of turn dim. The highlight takes the style's second hue.
PANEL_SECONDS = 2.5
_PANEL_FADE = 0.6
_PANEL_DIM = 0.65
# A table past this many rows is cut, with a last row counting the rest.
MAX_TABLE_ROWS = 30

_REPEAT = "repeat"
_OVER_TIME = "over_time"
_FRAME_GID = "bnframe"
_PANEL_GID = "bnpanel"
_GLOW_GID = "bnglow"
# Set on a grid figure: the panels' axes, so a decorate call draws one shared colour bar.
_PANELS_ATTR = "_bencher_svg_panels"
_FONT_STACK = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
# matplotlib's tab10, inlined so drawing a chart never touches the colormap registry.
_HUE_COLOURS = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)
_MAX_TICKS = 10
# 9 pt on a 6.4 in figure is 15.6 px when GitHub shows the SVG 800 px wide; the charts
# added for distributions and tables keep every label at or above it.
_MIN_FONT = 9
_MEDIAN_COLOUR = "#222222"
_GOLDEN = 0.6180339887
# A density needs a spread, so a violin needs at least two samples.
_MIN_KDE_SAMPLES = 2
# A surface or a contour needs at least two samples along each of its axes.
_MIN_GRID_SAMPLES = 2
# Up to this many panels sit in rows of three; past it, rows of four or more.
_THREE_COLUMN_PANELS = 9


@dataclass(frozen=True)
class _Layout:
    """Which dataset dims a chart shows on its axes; every other dim is a frame dim."""

    x: str | None = None
    y: str | None = None
    hue: str | None = None

    def shown(self) -> tuple[str, ...]:
        return tuple(d for d in (self.x, self.y, self.hue) if d is not None)

    def x_dim(self) -> str:
        """The x-axis dim of a layout that has one."""
        if self.x is None:
            raise ValueError(f"layout {self} has no x dim")
        return self.x

    def y_dim(self) -> str:
        """The y-axis dim of a two-axis (heatmap) layout."""
        if self.y is None:
            raise ValueError(f"layout {self} has no y dim; only a heatmap layout has one")
        return self.y


@dataclass(frozen=True)
class _Ctx:
    """Values fixed across frames: limits, colours, and any per-chart scale."""

    lo: float
    hi: float
    hue_values: tuple = ()
    ylabel: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SvgChart:
    """One chart type of the svg backend that draws a result var's values.

    ``match`` is the sweep shapes it draws (the registry checks it before selection),
    ``result_types`` the result vars it draws, ``layout`` picks the shown dims from the
    float and categorical input names and the data (``None``: nothing to draw), and
    ``draw`` draws one frame. ``keep_repeats`` hands each frame every repeat instead of
    their mean; ``framed=False`` shows every dim at once instead of animating;
    ``numeric=False`` keeps the values as they are (the table). ``decorate`` draws what
    is fixed across frames, ``prepare`` computes a scale fixed across frames, and
    ``auto=False`` makes it named-only, like its twin. ``projection="3d"`` draws on 3D
    axes (the surface).
    """

    name: str
    match: PlotFilter
    result_types: tuple[type, ...]
    layout: Callable[[list[str], list[str], xr.DataArray], _Layout | None]
    draw: Callable[[Axes, xr.DataArray, xr.DataArray | None, _Layout, _Ctx], list[Any]]
    figsize: tuple[float, float] | Callable[[xr.DataArray], tuple[float, float]] = (6.4, 4.0)
    keep_repeats: bool = False
    framed: bool = True
    numeric: bool = True
    decorate: Callable[..., None] | None = None
    prepare: Callable[[xr.DataArray, _Layout], dict[str, Any]] | None = None
    title: Callable[[str, _Layout], str] | None = None
    auto: bool = True
    projection: str | None = None


# ---------------------------------------------------------------- formatting


def _fmt(value: Any) -> str:
    if isinstance(value, np.datetime64):
        text = np.datetime_as_string(value, unit="s").replace("T", " ")
        return text.removesuffix(" 00:00:00")
    if isinstance(value, (float, np.floating)):
        return f"{value:.4g}"
    return str(value.item() if isinstance(value, np.generic) else value)


def _categorical_ticks(ax_set: Callable, labels: list[str]) -> None:
    step = max(1, int(np.ceil(len(labels) / _MAX_TICKS)))
    idx = list(range(0, len(labels), step))
    ax_set(idx, [labels[i] for i in idx])


def _is_axis_valued(values: np.ndarray) -> bool:
    """Whether coords can sit on an axis as they are (numbers, times), not as positions."""
    return bool(
        np.issubdtype(values.dtype, np.number) or np.issubdtype(values.dtype, np.datetime64)
    )


def _colour(i: int, n: int = 0) -> str:
    """Hue ``i`` of ``n`` (0: not known) in the active style's palette."""
    return _style().colour(i, n)


# ---------------------------------------------------------------- styles
#
# A style is the look every chart of one render shares: colours, axes face and grid, line
# and text sizes. ``plain`` is plain matplotlib (tab10, white axes); the seaborn styles
# draw the panels with seaborn and theme every chart, matplotlib-drawn ones included, with
# a seaborn axes style, plotting context and palette. The style is active only while one
# chart draws (:func:`_draw_frames` sets it and puts back the old one), next to the
# ``rc_context`` that carries its rc, so a render never changes global state.

SVG_STYLES = ("seaborn", "seaborn-ticks", "plain")
# seaborn's "notebook" context with its tick labels (its smallest text) at 10 pt, 17 px
# when GitHub shows a 6.4 in figure 800 px wide: above the 9 pt floor, with room to spare.
_SNS_FONT_SCALE = 10 / 11
# Up to this many hues take seaborn's "deep" palette; past it "husl", which never repeats.
_SNS_DEEP = 10


@dataclass(frozen=True)
class _Style:
    """What one svg style sets. The defaults are ``plain``, the look without seaborn."""

    name: str = "plain"
    sns: ModuleType | None = None
    rc: Mapping[str, Any] = field(default_factory=dict)
    palette: tuple[str, ...] = _HUE_COLOURS
    # Whether the charts that ask for a grid get one (the ticks style has none).
    grid: bool = True
    grid_alpha: float | None = 0.3
    despine: bool = False
    font: float = _MIN_FONT
    hue_legend_font: float = 8
    median: str = _MEDIAN_COLOUR
    heat_cmap: Any = "plasma"
    volume_cmap: Any = "viridis"
    table_edge: str = "#cccccc"
    table_head: str = "#eeeeee"
    table_body: str | None = None

    @property
    def accent(self) -> str:
        """The colour of the highlight that walks a grid's panels."""
        return self.palette[1]

    def colour(self, i: int, n: int = 0) -> str:
        if self.sns is None or n <= len(self.palette):
            return self.palette[i % len(self.palette)]
        return _sns_palette(self.sns, "husl", n)[i]


_PLAIN = _Style()
_STYLE: contextvars.ContextVar[_Style] = contextvars.ContextVar("bencher_svg_style", default=_PLAIN)
_warned_no_seaborn = False


def _style() -> _Style:
    """The style of the chart drawing now (``plain`` outside a draw)."""
    return _STYLE.get()


@functools.lru_cache(maxsize=64)
def _sns_palette(sns: ModuleType, name: str, n: int) -> tuple[str, ...]:
    """A seaborn palette as hex strings, so the bytes never carry float noise."""
    from matplotlib.colors import to_hex

    return tuple(to_hex(c) for c in sns.color_palette(name, n))


def _sns_style(sns: ModuleType, name: str) -> _Style:
    """A seaborn style: ``seaborn`` is darkgrid, ``seaborn-ticks`` ticks with no top/right."""
    from cycler import cycler

    dark = name == "seaborn"
    axes = sns.axes_style("darkgrid" if dark else "ticks")
    palette = _sns_palette(sns, "deep", _SNS_DEEP)
    rc = {
        # The style's fonts (Arial first) are dropped: the text must not depend on the host.
        **{k: v for k, v in axes.items() if not k.startswith("font.")},
        **sns.plotting_context("notebook", font_scale=_SNS_FONT_SCALE),
        # Only the charts that ask for a grid get one (not tables, heatmaps, colour bars).
        "axes.grid": False,
        "axes.prop_cycle": cycler(color=palette),
        "axes3d.xaxis.panecolor": axes["axes.facecolor"],
        "axes3d.yaxis.panecolor": axes["axes.facecolor"],
        "axes3d.zaxis.panecolor": axes["axes.facecolor"],
    }
    font = 11 * _SNS_FONT_SCALE
    return _Style(
        name=name,
        sns=sns,
        rc=rc,
        palette=palette,
        grid=dark,
        grid_alpha=None,
        despine=not dark,
        font=font,
        hue_legend_font=font,
        median="#262626",
        heat_cmap=sns.color_palette("rocket", as_cmap=True),
        volume_cmap=sns.color_palette("mako", as_cmap=True),
        table_edge="white" if dark else "#cccccc",
        table_head="#d5d5e3" if dark else "#eaeaf2",
        table_body=axes["axes.facecolor"] if dark else None,
    )


def _resolve_style(name: str) -> _Style:
    """The style named ``name``; without seaborn every name is ``plain`` (one warning)."""
    global _warned_no_seaborn  # noqa: PLW0603 - warn once per process, not once per chart
    if name not in SVG_STYLES:
        raise ValueError(f"svg_style must be one of {SVG_STYLES}, not {name!r}")
    if name == "plain":
        return _PLAIN
    sns = _seaborn()
    if sns is None:
        if not _warned_no_seaborn:
            _warned_no_seaborn = True
            log.warning(
                "svg_style=%r needs seaborn (the holobench[seaborn] extra); drawing 'plain'", name
            )
        return _PLAIN
    return _sns_style(sns, name)


def _grid(ax: Axes, axis: str = "both") -> None:
    """The grid a chart asks for, in the style's look (none in the ticks style)."""
    style = _style()
    if style.grid_alpha is not None:
        ax.grid(True, axis=axis, alpha=style.grid_alpha)
    elif style.grid:
        ax.grid(True, axis=axis)


# ---------------------------------------------------------------- layouts


def _layout_line(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout:
    del da
    return _Layout(x=floats[0], hue=cats[0] if cats else None)


def _layout_heatmap(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout:
    del da
    axes = [*floats, *cats]
    return _Layout(x=axes[0], y=axes[1])


def _layout_bar(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout:
    del floats, da
    return _Layout(x=cats[0], hue=cats[1] if len(cats) > 1 else None)


def _layout_groups(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout:
    """First cat on x (none: one group), second as the hue."""
    del floats, da
    return _Layout(x=cats[0] if cats else None, hue=cats[1] if len(cats) > 1 else None)


def _layout_none(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout:
    del floats, cats, da
    return _Layout()


def _layout_band(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout | None:
    """The twin's x: over_time when it has several steps, else the first other dim."""
    del floats, cats
    if da.sizes.get(_OVER_TIME, 0) > 1:
        return _Layout(x=_OVER_TIME)
    candidates = [str(d) for d in da.dims if d not in (_REPEAT, _OVER_TIME)]
    return _Layout(x=candidates[0]) if candidates else None


# ---------------------------------------------------------------- value-chart drawers


def _hue_slices(da: xr.DataArray, layout: _Layout, ctx: _Ctx) -> list[tuple[int, Any, Any]]:
    """(colour index, hue value, slice) for each hue level, or one slice without a hue."""
    if layout.hue is None:
        return [(0, None, da)]
    return [(i, v, da.sel({layout.hue: v})) for i, v in enumerate(ctx.hue_values)]


def _draw_line(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    artists: list[Any] = []
    x = da[layout.x_dim()].values
    parts = _hue_slices(da, layout, ctx)
    for i, _value, part in parts:
        artists += ax.plot(
            x, part.transpose(layout.x_dim()).values, color=_colour(i, len(parts)), marker="o", ms=3
        )
    return artists


def _draw_curve(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    artists: list[Any] = []
    x_dim = layout.x_dim()
    x = da[x_dim].values
    spread = std if std is not None else da * 0.0
    parts = _hue_slices(da, layout, ctx)
    for i, value, part in parts:
        colour = _colour(i, len(parts))
        dev = spread.sel({layout.hue: value}) if layout.hue is not None else spread
        mean = part.transpose(x_dim).values
        dev_values = dev.transpose(x_dim).values
        artists.append(
            ax.fill_between(x, mean - dev_values, mean + dev_values, color=colour, alpha=0.25, lw=0)
        )
        artists += ax.plot(x, mean, color=colour)
    return artists


def _draw_heatmap(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    z = da.transpose(layout.y_dim(), layout.x_dim()).values.astype(float)
    # interpolation="none" embeds the cell grid as one tiny inline PNG drawn with
    # pixelated scaling: crisp cells at a fraction of the size of one path per cell.
    mesh = ax.imshow(
        z,
        cmap=_style().heat_cmap,
        vmin=ctx.lo,
        vmax=ctx.hi,
        origin="lower",
        interpolation="none",
        aspect="auto",
    )
    return [mesh]


def _draw_bar(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    parts = _hue_slices(da, layout, ctx)
    width = 0.8 / len(parts)
    x_dim = layout.x_dim()
    n = da.sizes[x_dim]
    artists: list[Any] = []
    for i, _value, part in parts:
        offset = (i - (len(parts) - 1) / 2) * width
        bars = ax.bar(
            np.arange(n) + offset, part.transpose(x_dim).values, width, color=_colour(i, len(parts))
        )
        artists += list(bars.patches)
    return artists


# ---------------------------------------------------------------- distribution drawers


@dataclass(frozen=True)
class _Group:
    """One box/violin/strip: where it sits, its colour, and its samples."""

    pos: float
    colour: str
    width: float
    samples: np.ndarray


def _groups(da: xr.DataArray, layout: _Layout, ctx: _Ctx) -> list[_Group]:
    """One group per (x level, hue level) of a frame, with its finite samples."""
    parts = _hue_slices(da, layout, ctx)
    width = 0.8 / len(parts)
    n = da.sizes[layout.x] if layout.x is not None else 1
    groups = []
    for xi in range(n):
        for i, _value, part in parts:
            cell = part.isel({layout.x: xi}) if layout.x is not None else part
            values = np.asarray(cell.values, dtype=float).ravel()
            pos = xi + (i - (len(parts) - 1) / 2) * width
            groups.append(_Group(pos, _colour(i, len(parts)), width, values[np.isfinite(values)]))
    return groups


def _spread(samples: np.ndarray, width: float) -> np.ndarray:
    """Deterministic horizontal offsets: neighbours in value land far apart in x.

    A golden-ratio sequence over the value rank spreads a strip evenly without a random
    seed, so the same data draws the same bytes.
    """
    n = samples.size
    offsets = np.empty(n)
    order = np.argsort(samples, kind="stable")
    offsets[order] = ((np.arange(n) * _GOLDEN + 0.5) % 1.0 - 0.5) * width * 0.6
    return offsets


def _dots(ax: Axes, group: _Group, *, jitter: bool = True, size: float = 14) -> list[Any]:
    if group.samples.size == 0:
        return []
    offsets = _spread(group.samples, group.width) if jitter else np.zeros(group.samples.size)
    return [
        ax.scatter(
            group.pos + offsets,
            group.samples,
            s=size,
            color=group.colour,
            alpha=0.65,
            linewidths=0.4,
            edgecolors="white",
            zorder=3,
        )
    ]


def _median_mark(ax: Axes, group: _Group) -> list[Any]:
    if group.samples.size == 0:
        return []
    half = group.width * 0.4
    median = float(np.median(group.samples))
    return [
        ax.hlines(
            median, group.pos - half, group.pos + half, colors=_style().median, lw=3, zorder=4
        )
    ]


def _box(ax: Axes, group: _Group) -> list[Any]:
    from matplotlib.patches import Rectangle

    s = group.samples
    if s.size == 0:
        return []
    q1, q3 = np.percentile(s, [25, 75])
    iqr = q3 - q1
    lo = s[s >= q1 - 1.5 * iqr].min()
    hi = s[s <= q3 + 1.5 * iqr].max()
    half = group.width * 0.35
    rect = Rectangle(
        (group.pos - half, q1),
        2 * half,
        q3 - q1,
        facecolor=group.colour,
        alpha=0.2,
        edgecolor=group.colour,
        lw=1.2,
        zorder=2,
    )
    ax.add_patch(rect)
    whiskers = ax.vlines(
        [group.pos, group.pos], [lo, q3], [q1, hi], colors=group.colour, lw=1.2, zorder=2
    )
    return [rect, whiskers]


def _kde(samples: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """A Gaussian kernel density with Scott's bandwidth (no scipy needed)."""
    bw = 1.06 * samples.std() * samples.size ** (-1 / 5)
    z = (grid[:, None] - samples[None, :]) / bw
    return np.exp(-0.5 * z**2).sum(axis=1)


def _violin(ax: Axes, group: _Group, ctx: _Ctx) -> list[Any]:
    s = group.samples
    if s.size < _MIN_KDE_SAMPLES or s.std() == 0:
        return []
    bw = 1.06 * s.std() * s.size ** (-1 / 5)
    margin = (ctx.hi - ctx.lo) * _group_pad(ctx)
    grid = np.linspace(
        max(s.min() - 2 * bw, ctx.lo - margin), min(s.max() + 2 * bw, ctx.hi + margin), 64
    )
    density = _kde(s, grid)
    half = density / density.max() * group.width * 0.45
    return [
        ax.fill_betweenx(
            grid, group.pos - half, group.pos + half, color=group.colour, alpha=0.25, lw=0, zorder=2
        )
    ]


def _violin_pad(data: xr.DataArray, layout: _Layout) -> dict[str, Any]:
    """Room above and below the samples for the violins' tails."""
    del data, layout
    return {"pad": 0.15}


def _group_pad(ctx: _Ctx) -> float:
    return float(ctx.extra.get("pad", 0.05))


def _draw_box_whisker(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    artists: list[Any] = []
    for group in _groups(da, layout, ctx):
        artists += _box(ax, group) + _dots(ax, group) + _median_mark(ax, group)
    return artists


def _draw_violin(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    artists: list[Any] = []
    for group in _groups(da, layout, ctx):
        artists += _violin(ax, group, ctx) + _dots(ax, group) + _median_mark(ax, group)
    return artists


def _draw_scatter_jitter(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    artists: list[Any] = []
    for group in _groups(da, layout, ctx):
        artists += _dots(ax, group) + _median_mark(ax, group)
    return artists


def _draw_scatter(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std
    artists: list[Any] = []
    for group in _groups(da, layout, ctx):
        artists += _dots(ax, group, jitter=False, size=40)
    return artists


def _decorate_groups(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    """Fixed axes of a chart with one group per category: ticks, limits, legend."""
    del fig, chart
    from matplotlib.patches import Patch

    ax.set_title(title)
    ax.autoscale(False)
    n = data.sizes[layout.x] if layout.x is not None else 1
    ax.set_xlim(-0.5, n - 0.5)
    margin = (ctx.hi - ctx.lo) * _group_pad(ctx)
    ax.set_ylim(ctx.lo - margin, ctx.hi + margin)
    if layout.x is not None:
        ax.set_xlabel(layout.x)
        _categorical_ticks(ax.set_xticks, [_fmt(v) for v in data[layout.x].values])
    else:
        ax.set_xticks([])
    ax.set_ylabel(ctx.ylabel or str(data.name))
    _grid(ax, "y")
    if layout.hue is not None:
        n = len(ctx.hue_values)
        handles = [Patch(color=_colour(i, n), label=_fmt(v)) for i, v in enumerate(ctx.hue_values)]
        font = _style().font
        ax.legend(handles=handles, title=layout.hue, fontsize=font, title_fontsize=font)


# ---------------------------------------------------------------- histogram


def _hist_scale(data: xr.DataArray, layout: _Layout) -> dict[str, Any]:
    """Bin edges and the tallest bin over every frame, so frames share both axes."""
    del layout
    values = np.asarray(data.values, dtype=float)
    finite = values[np.isfinite(values)]
    lo, hi = _finite_limits(finite)
    n_samples = data.sizes.get(_REPEAT, 1)
    bins = int(np.clip(np.ceil(np.sqrt(n_samples)), 5, 30))
    edges = np.linspace(lo, hi, bins + 1)
    rows = (
        np.moveaxis(values, list(data.dims).index(_REPEAT), -1).reshape(-1, n_samples)
        if _REPEAT in data.dims
        else values.reshape(1, -1)
    )
    tallest = max((np.histogram(r[np.isfinite(r)], edges)[0].max() for r in rows), default=1)
    return {"edges": edges, "tallest": max(int(tallest), 1)}


def _draw_histogram(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std, layout
    edges = ctx.extra["edges"]
    tallest = ctx.extra["tallest"]
    values = np.asarray(da.values, dtype=float).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return []
    counts, _ = np.histogram(values, edges)
    bars = ax.stairs(counts, edges, fill=True, color=_colour(0), alpha=0.35)
    return [bars, *_hist_marks(ax, values, tallest)]


def _hist_marks(ax: Axes, values: np.ndarray, tallest: int) -> list[Any]:
    """Every sample as a dot in a strip under the bars, and the median across both."""
    order = np.argsort(values, kind="stable")
    lift = np.empty(values.size)
    lift[order] = (np.arange(values.size) * _GOLDEN + 0.5) % 1.0
    rug = ax.scatter(
        values,
        -tallest * (0.04 + 0.08 * lift),
        s=14,
        color=_colour(0),
        alpha=0.65,
        linewidths=0.4,
        edgecolors="white",
        zorder=3,
    )
    median = ax.vlines(
        float(np.median(values)),
        -tallest * 0.13,
        tallest * 1.05,
        colors=_style().median,
        lw=3,
        zorder=4,
    )
    return [rug, median]


def _decorate_histogram(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    del fig, chart, layout
    edges = ctx.extra["edges"]
    tallest = ctx.extra["tallest"]
    ax.set_title(title)
    ax.autoscale(False)
    ax.set_xlim(edges[0], edges[-1])
    ax.set_ylim(-tallest * 0.15, tallest * 1.1)
    ax.set_xlabel(ctx.ylabel or str(data.name))
    ax.set_ylabel("count")
    _grid(ax, "y")


# ---------------------------------------------------------------- band


def _band_values(da: xr.DataArray, x_dim: str) -> np.ndarray:
    """(n_x, n_samples): every dim but x pooled into the samples, as the twin does."""
    others = [str(d) for d in da.dims if d != x_dim]
    if not others:
        return np.asarray(da.values, dtype=float)[:, None]
    stacked = da.stack(sample=others)  # noqa: PD013 - xarray stack, not pandas
    return np.asarray(stacked.transpose(x_dim, "sample").values, dtype=float)


def _x_positions(coords: np.ndarray) -> np.ndarray:
    return coords if _is_axis_valued(coords) else np.arange(coords.size)


def _draw_band(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std, ctx
    x_dim = layout.x_dim()
    values = _band_values(da, x_dim)
    x = _x_positions(da[x_dim].values)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # an all-NaN column
        p10, p25, p50, p75, p90 = np.nanpercentile(values, [10, 25, 50, 75, 90], axis=1)
    colour = _colour(0)
    artists: list[Any] = [
        ax.fill_between(x, p10, p90, color=colour, alpha=0.15, lw=0, label="10-90%"),
        ax.fill_between(x, p25, p75, color=colour, alpha=0.3, lw=0, label="25-75%"),
    ]
    flat_x = np.repeat(x, values.shape[1])
    artists.append(
        ax.scatter(flat_x, values.ravel(), s=10, color=colour, alpha=0.45, linewidths=0, zorder=3)
    )
    artists += ax.plot(x, p50, color=_style().median, lw=3, zorder=4, label="median")
    return artists


def _decorate_band(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    del fig, chart
    x_dim = layout.x_dim()
    coords = data[x_dim].values
    ax.set_title(title)
    ax.autoscale(False)
    if not _is_axis_valued(coords):
        ax.set_xlim(-0.5, coords.size - 0.5)
        _categorical_ticks(ax.set_xticks, [_fmt(v) for v in coords])
    elif coords.size > 1:
        ax.set_xlim(coords.min(), coords.max())
    elif np.issubdtype(coords.dtype, np.number):
        ax.set_xlim(float(coords[0]) - 0.5, float(coords[0]) + 0.5)
    margin = (ctx.hi - ctx.lo) * 0.05
    ax.set_ylim(ctx.lo - margin, ctx.hi + margin)
    ax.set_xlabel(x_dim)
    ax.set_ylabel(ctx.ylabel or str(data.name))
    _grid(ax)


def _legend_band(ax: Axes) -> None:
    ax.legend(fontsize=_style().font, loc="best")


# ---------------------------------------------------------------- surface and volume


def _layout_surface(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout | None:
    """The twin's two floats as x and y; a float with one sample draws no surface."""
    del cats
    if any(da.sizes[f] < _MIN_GRID_SAMPLES for f in floats[:2]):
        return None
    return _Layout(x=floats[0], y=floats[1])


def _layout_volume(floats: list[str], cats: list[str], da: xr.DataArray) -> _Layout | None:
    """The twin's first two floats as x and y; the third is the dim of the slice panels.

    ``None`` (the twin's fallback) over time, which the twin skips, and for an x or y
    with one sample, which has no contour.
    """
    if _OVER_TIME in da.dims:
        return None
    return _layout_surface(floats, cats, da)


def _volume_levels(data: xr.DataArray, layout: _Layout) -> dict[str, Any]:
    """Contour levels fixed across slices: the twin's isomin..isomax in equal steps."""
    del layout
    lo, hi = _finite_limits(data.values)
    return {"levels": np.linspace(lo, hi, 13)}


def _draw_volume(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    """One slice of the volume: filled iso-bands of x and y, like the twin's isosurfaces."""
    del std
    x_dim, y_dim = layout.x_dim(), layout.y_dim()
    z = da.transpose(y_dim, x_dim).values.astype(float)
    if not np.isfinite(z).any():
        return []
    x = da[x_dim].values.astype(float)
    y = da[y_dim].values.astype(float)
    levels = ctx.extra["levels"]
    bands = ax.contourf(x, y, z, levels=levels, cmap=_style().volume_cmap, vmin=ctx.lo, vmax=ctx.hi)
    edges = ax.contour(x, y, z, levels=levels, colors="white", linewidths=0.5, alpha=0.6)
    return [bands, edges]


def _decorate_volume(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize

    del chart
    x_dim, y_dim = layout.x_dim(), layout.y_dim()
    xs, ys = data[x_dim].values, data[y_dim].values
    ax.set_title(title)
    ax.autoscale(False)
    ax.set_xlim(xs.min(), xs.max())
    ax.set_ylim(ys.min(), ys.max())
    ax.set_xlabel(x_dim)
    ax.set_ylabel(y_dim)
    mappable = ScalarMappable(norm=Normalize(ctx.lo, ctx.hi), cmap=_style().volume_cmap)
    _colorbar(fig, ax, mappable, ctx.ylabel or str(data.name))


def _draw_surface(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    """The mean surface, and every repeat as a dot over its grid point."""
    del std
    x_dim, y_dim = layout.x_dim(), layout.y_dim()
    gx, gy = np.meshgrid(da[x_dim].values.astype(float), da[y_dim].values.astype(float))
    mean = da.mean(_REPEAT) if _REPEAT in da.dims else da
    z = mean.transpose(y_dim, x_dim).values.astype(float)
    surface = ax.plot_surface(  # ty: ignore[unresolved-attribute] - 3D axes
        gx,
        gy,
        z,
        cmap=_style().volume_cmap,
        vmin=ctx.lo,
        vmax=ctx.hi,
        rstride=1,
        cstride=1,
        linewidth=0.3,
        edgecolor="#ffffff",
        antialiased=False,
    )
    artists: list[Any] = [surface]
    if da.sizes.get(_REPEAT, 1) > 1:
        samples = da.transpose(y_dim, x_dim, _REPEAT).values.astype(float)
        shape = samples.shape
        # A 3D scatter takes (xs, ys, zs); the 2D signature types the third as ``s``.
        style = {"s": 8, "color": _style().median, "alpha": 0.7, "depthshade": False}
        dots = ax.scatter(
            np.broadcast_to(gx[..., None], shape).ravel(),
            np.broadcast_to(gy[..., None], shape).ravel(),
            samples.ravel(),
            **style,
        )
        artists.append(dots)
    return artists


def _decorate_surface(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    """Fixed limits and a fixed camera: the twin's view, without the mouse."""
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize

    del chart
    x_dim, y_dim = layout.x_dim(), layout.y_dim()
    xs, ys = data[x_dim].values, data[y_dim].values
    label = ctx.ylabel or str(data.name)
    margin = (ctx.hi - ctx.lo) * 0.05
    ax.set_title(title)
    ax.set_xlim(xs.min(), xs.max())
    ax.set_ylim(ys.min(), ys.max())
    ax.set_zlim(ctx.lo - margin, ctx.hi + margin)  # ty: ignore[unresolved-attribute]
    ax.set_xlabel(x_dim)
    ax.set_ylabel(y_dim)
    # The colour bar names the value; a z label would sit outside the figure.
    ax.view_init(elev=28, azim=-60)  # ty: ignore[unresolved-attribute]
    # Shrunk a little so the tick labels stay inside the axes' box, clear of a neighbour.
    ax.set_box_aspect(None, zoom=0.85)  # ty: ignore[unknown-argument]
    if _style().sns is not None:
        # The style's face colour goes on the panes (rc); the box round them is the page's.
        ax.set_facecolor(fig.get_facecolor())
    mappable = ScalarMappable(norm=Normalize(ctx.lo, ctx.hi), cmap=_style().volume_cmap)
    _colorbar(fig, ax, mappable, label)


# ---------------------------------------------------------------- table


def _table_dims(da: xr.DataArray) -> list[str]:
    """The table's index columns: every dim with more than one value (the twin squeezes)."""
    return [str(d) for d in da.dims if da.sizes[d] > 1]


def _table_rows(da: xr.DataArray) -> tuple[list[str], list[list[str]], int]:
    """(header, first MAX_TABLE_ROWS rows, total row count) of one result var."""
    squeezed = da.squeeze(drop=False)
    dims = _table_dims(da)
    squeezed = squeezed.transpose(*dims) if dims else squeezed
    coords = [squeezed[d].values for d in dims]
    values = squeezed.values
    total = int(np.prod([c.size for c in coords])) if coords else 1
    indices = itertools.islice(itertools.product(*(range(c.size) for c in coords)), MAX_TABLE_ROWS)
    rows = [
        [*(_fmt(c[i]) for c, i in zip(coords, idx, strict=True)), _fmt(values[idx])]
        for idx in indices
    ]
    return [*dims, str(da.name)], rows, total


def _table_figsize(da: xr.DataArray) -> tuple[float, float]:
    _header, rows, total = _table_rows(da)
    lines = len(rows) + 1 + (1 if total > len(rows) else 0)
    return 6.4, 0.7 + 0.28 * lines


def _draw_table(
    ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
) -> list[Any]:
    del std, layout, ctx
    header, rows, total = _table_rows(da)
    if total > len(rows):
        rows.append([f"... {total - len(rows)} more rows", *([""] * (len(header) - 1))])
    table = ax.table(cellText=rows, colLabels=header, cellLoc="center", bbox=(0, 0, 1, 1))
    table.auto_set_font_size(False)
    style = _style()
    table.set_fontsize(style.font)
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor(style.table_edge)
        if row == 0:
            cell.set_facecolor(style.table_head)
            cell.get_text().set_fontweight("bold")
        elif style.table_body is not None:
            cell.set_facecolor(style.table_body)
    return [table]


def _decorate_table(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    data: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    del fig, chart, data, layout, ctx
    ax.set_title(title)
    ax.axis("off")


# ---------------------------------------------------------------- seaborn drawers
#
# With seaborn installed (the ``seaborn`` extra) and a seaborn style, the value and
# distribution charts draw each panel with it: a true beeswarm of every repeat, seaborn's
# boxes, violins, histogram and lines. In ``plain``, or without seaborn, they draw the
# same charts with plain matplotlib, above.
# Either way the drawer draws into the panel's Axes after ``decorate`` fixed its limits,
# ticks and labels, and :func:`_sns_artists` puts those back after seaborn moves them, so
# the grid, the frames and the highlight walk do not know which one drew.

# Dot diameter of a beeswarm, in points: seaborn's default.
_SWARM_SIZE = 5.0
# The dark grey seaborn's docs draw a beeswarm in over boxes (as matplotlib colour text).
_SWARM_DARK = "0.25"
# The share of an Axes' nominal size its plot area keeps after constrained layout.
_LAYOUT_SHARE = 0.8
# A heatmap cell smaller than this (points) keeps the matplotlib image: white gaps
# between cells that small would hide the cells, and one path per cell bloats the SVG.
_SNS_HEATMAP_CELL = 10.0
# A heatmap cell this big (points) has room for its value written in it.
_ANNOT_CELL = (30.0, 14.0)


# The oldest seaborn whose API the seaborn drawers use (e.g. violinplot's density_norm).
_MIN_SEABORN = (0, 13)


def _seaborn() -> ModuleType | None:
    """The seaborn module, or None when the ``seaborn`` extra is not installed or unusable.

    An import that fails any way, or a seaborn older than ``_MIN_SEABORN``, counts as not
    installed, so every chart still draws with matplotlib.
    """
    try:
        import seaborn as sns
    except Exception:  # noqa: BLE001
        return None
    version = tuple(int(part) for part in re.findall(r"\d+", getattr(sns, "__version__", ""))[:2])
    if version < _MIN_SEABORN:
        return None
    return sns


def _either(
    plain: Callable[[Axes, xr.DataArray, xr.DataArray | None, _Layout, _Ctx], list[Any]],
    seaborn: Callable[..., list[Any]],
) -> Callable[[Axes, xr.DataArray, xr.DataArray | None, _Layout, _Ctx], list[Any]]:
    """A drawer that uses ``seaborn`` in a seaborn style, else the matplotlib ``plain``."""

    def draw(
        ax: Axes, da: xr.DataArray, std: xr.DataArray | None, layout: _Layout, ctx: _Ctx
    ) -> list[Any]:
        sns = _style().sns
        if sns is None:
            return plain(ax, da, std, layout, ctx)
        return seaborn(sns, ax, da, std, layout, ctx)

    draw.__name__ = plain.__name__
    draw.__doc__ = plain.__doc__
    return draw


def _sns_artists(ax: Axes, plot: Callable[[], object]) -> list[Any]:
    """Run ``plot`` (a seaborn call on ``ax``) and return the artists it added, in order.

    Seaborn sets its own limits, ticks, labels and grid on the Axes it draws into; the
    chart's ``decorate`` already set them, fixed across frames and panels, so they are
    put back.
    """
    xaxis, yaxis = ax.xaxis, ax.yaxis
    state = (
        ax.get_xlim(),
        ax.get_ylim(),
        ax.get_xlabel(),
        ax.get_ylabel(),
        xaxis.get_major_locator(),
        xaxis.get_major_formatter(),
        yaxis.get_major_locator(),
        yaxis.get_major_formatter(),
        ax.get_autoscalex_on(),
        ax.get_autoscaley_on(),
        [line.get_visible() for line in xaxis.get_gridlines()][:1],
    )
    before = {id(child) for child in ax.get_children()}
    with warnings.catch_warnings():
        # pandas and seaborn deprecation chatter, nothing that changes the drawing.
        warnings.simplefilter("ignore", FutureWarning)
        warnings.simplefilter("ignore", DeprecationWarning)
        # A categorical plot sizes the x limits from the tick count, which is 0 for a
        # chart with no x levels; the limits are put back below either way.
        warnings.filterwarnings("ignore", "Attempting to set identical", UserWarning)
        # Seaborn passes the category levels as strings, which matplotlib.category notes at
        # INFO on every call: noise in a bencher run, which logs at INFO.
        category_log = logging.getLogger("matplotlib.category")
        level = category_log.level
        category_log.setLevel(logging.WARNING)
        try:
            plot()
        finally:
            category_log.setLevel(level)
    (xlim, ylim, xlabel, ylabel, xloc, xfmt, yloc, yfmt, scalex, scaley, xgrid) = state
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    xaxis.set_major_locator(xloc)
    xaxis.set_major_formatter(xfmt)
    yaxis.set_major_locator(yloc)
    yaxis.set_major_formatter(yfmt)
    ax.set_autoscalex_on(scalex)
    ax.set_autoscaley_on(scaley)
    if xgrid:
        # A categorical seaborn plot switches the x grid off; keep the panel's own choice.
        ax.xaxis.grid(xgrid[0])
    return [child for child in ax.get_children() if id(child) not in before]


def _long(groups: list[_Group], layout: _Layout, ctx: _Ctx) -> pd.DataFrame:
    """Every finite sample of a frame as rows of (x level, hue level, value)."""
    import pandas as pd

    n_hue = max(1, len(ctx.hue_values)) if layout.hue is not None else 1
    xs, hues, values = [], [], []
    for k, group in enumerate(groups):
        xs.append(np.full(group.samples.size, k // n_hue))
        hues.append(np.full(group.samples.size, k % n_hue))
        values.append(group.samples)
    return pd.DataFrame(
        {
            "x": np.concatenate(xs) if xs else np.empty(0, int),
            "hue": np.concatenate(hues) if hues else np.empty(0, int),
            "v": np.concatenate(values) if values else np.empty(0),
        }
    )


def _categorical(da: xr.DataArray, layout: _Layout, ctx: _Ctx) -> dict[str, Any]:
    """Keywords that put seaborn's categories where ``_groups`` puts them.

    x levels sit at 0..n-1 and hue levels side by side, coloured like the legend.
    """
    n = da.sizes[layout.x] if layout.x is not None else 1
    kwargs: dict[str, Any] = {"x": "x", "y": "v", "order": list(range(n)), "legend": False}
    if layout.hue is None:
        return {**kwargs, "color": _colour(0)}
    levels = list(range(len(ctx.hue_values)))
    return {
        **kwargs,
        "hue": "hue",
        "hue_order": levels,
        "palette": {i: _colour(i, len(levels)) for i in levels},
        "dodge": True,
    }


def _crowd(samples: np.ndarray, span: float) -> int:
    """The most samples within any window of height ``span``: a beeswarm's widest row."""
    if samples.size == 0:
        return 0
    s = np.sort(samples)
    return int((np.searchsorted(s, s + span, side="right") - np.arange(s.size)).max())


def _swarm_fits(ax: Axes, groups: list[_Group]) -> bool:
    """Whether every group's beeswarm fits its width without piling dots at the edges.

    Seaborn places a swarm at draw time and, when it runs out of width, stacks the dots
    that do not fit on the group's edge. This estimate (from the Axes' nominal size, less
    what constrained layout takes) picks the jitter strip for those frames instead.
    """
    fig = ax.get_figure()
    if fig is None or not groups:
        return True
    box = ax.get_position()
    width_pt = box.width * fig.get_figwidth() * 72 * _LAYOUT_SHARE
    height_pt = box.height * fig.get_figheight() * 72 * _LAYOUT_SHARE
    lo, hi = ax.get_ylim()
    x_lo, x_hi = ax.get_xlim()
    if hi <= lo or x_hi <= x_lo or width_pt <= 0 or height_pt <= 0:
        return False
    span = _SWARM_SIZE / height_pt * (hi - lo)
    for group in groups:
        room = group.width * 0.8 / (x_hi - x_lo) * width_pt
        if _crowd(group.samples, span) * _SWARM_SIZE > room:
            return False
    return True


def _sns_dots(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    colour: str | None = None,
    edge: str | None = None,
) -> list[Any]:
    """Every repeat as a dot: a seaborn beeswarm, or the jitter strip when it would overflow.

    The dots take the hue colours, or one ``colour`` for all (over boxes or violins that
    already show the hue), with an ``edge`` line round each.
    """
    groups = _groups(da, layout, ctx)
    if not _swarm_fits(ax, groups):
        if colour is not None:
            # The strip's dots have a white edge: a white dot takes the edge colour instead.
            groups = [dataclasses.replace(g, colour=edge or colour) for g in groups]
        return [artist for group in groups for artist in _dots(ax, group)]
    data = _long(groups, layout, ctx)
    if data.empty:
        return []
    kwargs = _categorical(da, layout, ctx)
    if colour is not None:
        if "palette" in kwargs:
            kwargs["palette"] = dict.fromkeys(kwargs["palette"], colour)
        else:
            kwargs["color"] = colour
    return _sns_artists(
        ax,
        lambda: sns.swarmplot(
            data=data,
            ax=ax,
            size=_SWARM_SIZE,
            edgecolor=edge or "white",
            linewidth=0.5 if edge else 0,
            warn_thresh=1.0,
            zorder=3,
            **kwargs,
        ),
    )


def _medians(ax: Axes, da: xr.DataArray, layout: _Layout, ctx: _Ctx) -> list[Any]:
    return [artist for group in _groups(da, layout, ctx) for artist in _median_mark(ax, group)]


def _sns_box_whisker(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    data = _long(_groups(da, layout, ctx), layout, ctx)
    if data.empty:
        return []
    boxes = _sns_artists(
        ax,
        lambda: sns.boxplot(
            data=data,
            ax=ax,
            # Dodged over 0.8 like the swarm and _groups; the gap narrows each box.
            width=0.8,
            gap=0.125,
            # The dots show every repeat, outliers included.
            showfliers=False,
            **_categorical(da, layout, ctx),
        ),
    )
    # Seaborn's docs: a dark grey beeswarm over the boxes, which carry the hue.
    return boxes + _sns_dots(sns, ax, da, layout, ctx, colour=_SWARM_DARK)


def _sns_violin(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    # A density needs a spread: a group with fewer samples, or one value, shows its dots.
    groups = [
        dataclasses.replace(g, samples=g.samples[:0])
        if g.samples.size < _MIN_KDE_SAMPLES or g.samples.std() == 0
        else g
        for g in _groups(da, layout, ctx)
    ]
    data = _long(groups, layout, ctx)
    shapes = (
        []
        if data.empty
        else _sns_artists(
            ax,
            lambda: sns.violinplot(
                data=data,
                ax=ax,
                inner=None,
                cut=2,
                density_norm="width",
                **_categorical(da, layout, ctx),
            ),
        )
    )
    # Seaborn's docs: white dots edged in grey over the violins, which carry the hue.
    dots = _sns_dots(sns, ax, da, layout, ctx, colour="white", edge="0.3")
    return shapes + dots + _medians(ax, da, layout, ctx)


def _sns_scatter_jitter(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    return _sns_dots(sns, ax, da, layout, ctx) + _medians(ax, da, layout, ctx)


def _sns_scatter(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    groups = [g for g in _groups(da, layout, ctx) if g.samples.size]
    if not groups:
        return []
    xs = np.concatenate([np.full(g.samples.size, g.pos) for g in groups])
    ys = np.concatenate([g.samples for g in groups])
    colours = [g.colour for g in groups for _ in range(g.samples.size)]
    return _sns_artists(
        ax,
        lambda: sns.scatterplot(
            x=xs,
            y=ys,
            ax=ax,
            hue=colours,
            palette={colour: colour for colour in colours},
            s=60,
            legend=False,
            zorder=3,
        ),
    )


def _xy_frame(da: xr.DataArray, layout: _Layout, ctx: _Ctx, rows: Callable) -> pd.DataFrame:
    """Rows of (x, hue level, value) for a line or curve, one hue slice after another."""
    import pandas as pd

    frames = []
    for i, value, part in _hue_slices(da, layout, ctx):
        x, ys = rows(value, part)
        frames.append(pd.DataFrame({"x": np.tile(x, len(ys)), "hue": i, "v": np.concatenate(ys)}))
    return pd.concat(frames, ignore_index=True)


def _line_kwargs(layout: _Layout, ctx: _Ctx) -> dict[str, Any]:
    if layout.hue is None:
        return {"color": _colour(0)}
    levels = list(range(len(ctx.hue_values)))
    palette = {i: _colour(i, len(levels)) for i in levels}
    return {"hue": "hue", "hue_order": levels, "palette": palette}


def _sns_line(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    x_dim = layout.x_dim()
    data = _xy_frame(
        da, layout, ctx, lambda _v, part: (part[x_dim].values, [part.transpose(x_dim).values])
    )
    return _sns_artists(
        ax,
        lambda: sns.lineplot(
            data=data,
            x="x",
            y="v",
            ax=ax,
            marker="o",
            # Seaborn's white-edged markers, small enough that 25 points keep a line.
            markersize=4.5,
            markeredgewidth=0.6,
            errorbar=None,
            legend=False,
            **_line_kwargs(layout, ctx),
        ),
    )


def _sns_curve(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    x_dim = layout.x_dim()
    spread = std if std is not None else da * 0.0

    def rows(value: Any, part: xr.DataArray) -> tuple[np.ndarray, list[np.ndarray]]:
        dev = spread.sel({layout.hue: value}) if layout.hue is not None else spread
        mean = part.transpose(x_dim).values
        dev_values = dev.transpose(x_dim).values
        return part[x_dim].values, [mean - dev_values, mean + dev_values]

    # The frame holds each point's mean and standard deviation, not its repeats: two rows
    # per x at mean -/+ std make lineplot's own estimator the mean and its full-range
    # interval exactly the +/- 1 std band the matplotlib curve draws.
    return _sns_artists(
        ax,
        lambda: sns.lineplot(
            data=_xy_frame(da, layout, ctx, rows),
            x="x",
            y="v",
            ax=ax,
            estimator="mean",
            errorbar=("pi", 100),
            err_kws={"linewidth": 0},
            legend=False,
            **_line_kwargs(layout, ctx),
        ),
    )


def _sns_band(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    """Lineplot's percentile bands over the pooled samples, its median, and every sample."""
    import pandas as pd

    del std, ctx
    x_dim = layout.x_dim()
    values = _band_values(da, x_dim)
    x = _x_positions(da[x_dim].values)
    flat_x = np.repeat(x, values.shape[1])
    data = pd.DataFrame({"x": flat_x, "v": values.ravel()}).dropna()
    colour = _colour(0)
    artists: list[Any] = []
    # Seaborn's band alpha (0.2) outside, darker inside so the two read apart on a grey face.
    for interval, alpha, label in ((80, 0.2, "10-90%"), (50, 0.4, "25-75%")):
        drawn = _sns_artists(
            ax,
            lambda interval=interval, alpha=alpha: sns.lineplot(
                data=data,
                x="x",
                y="v",
                ax=ax,
                estimator="median",
                errorbar=("pi", interval),
                color=colour,
                err_kws={"alpha": alpha, "linewidth": 0},
                legend=False,
            ),
        )
        for artist in drawn:
            if hasattr(artist, "get_xydata"):
                # Each call draws the median line too; one median, drawn last, is enough.
                artist.remove()
            else:
                artist.set_label(label)
                artists.append(artist)
    artists += _sns_artists(
        ax,
        lambda: sns.scatterplot(
            x=flat_x, y=values.ravel(), ax=ax, s=12, color=colour, alpha=0.7, linewidth=0
        ),
    )
    artists += _sns_artists(
        ax,
        lambda: sns.lineplot(
            data=data,
            x="x",
            y="v",
            ax=ax,
            estimator="median",
            errorbar=None,
            color=_style().median,
            linewidth=2.5,
            zorder=4,
            label="median",
            legend=False,
        ),
    )
    return artists


def _sns_bar(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    del std
    data = _long(_groups(da, layout, ctx), layout, ctx)
    if data.empty:
        return []
    return _sns_artists(
        ax,
        lambda: sns.barplot(
            data=data,
            ax=ax,
            errorbar=None,
            **_categorical(da, layout, ctx),
        ),
    )


def _sns_heatmap(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    """Seaborn's heatmap: white gaps between cells, and each value written in a big cell."""
    from matplotlib.transforms import Affine2D

    z = da.transpose(layout.y_dim(), layout.x_dim()).values.astype(float)
    fig = ax.get_figure()
    box = ax.get_position()
    cell_w = box.width * fig.get_figwidth() * 72 * _LAYOUT_SHARE / z.shape[1] if fig else 0.0
    cell_h = box.height * fig.get_figheight() * 72 * _LAYOUT_SHARE / z.shape[0] if fig else 0.0
    if min(cell_w, cell_h) < _SNS_HEATMAP_CELL:
        return _draw_heatmap(ax, da, std, layout, ctx)
    annot: Any = False
    if cell_w >= _ANNOT_CELL[0] and cell_h >= _ANNOT_CELL[1]:
        # Two significant digits, with float noise (1e-17 for a zero) written as 0.
        noise = max(abs(ctx.lo), abs(ctx.hi)) * 1e-9
        annot = np.array(
            [
                [f"{0.0 if abs(v) < noise else v:.2g}" if np.isfinite(v) else "" for v in row]
                for row in z
            ]
        )
    # Seaborn puts cell i on [i, i+1]; the chart's axes put it on [i-0.5, i+0.5].
    shift = Affine2D().translate(-0.5, -0.5) + ax.transData
    return _sns_artists(
        ax,
        lambda: sns.heatmap(
            z,
            ax=ax,
            cmap=_style().heat_cmap,
            vmin=ctx.lo,
            vmax=ctx.hi,
            cbar=False,
            linewidths=0.5,
            linecolor="white",
            annot=annot,
            fmt="",
            annot_kws={"fontsize": _style().font, "transform": shift},
            xticklabels=False,
            yticklabels=False,
            transform=shift,
        ),
    )


def _sns_histogram(
    sns: ModuleType,
    ax: Axes,
    da: xr.DataArray,
    std: xr.DataArray | None,
    layout: _Layout,
    ctx: _Ctx,
) -> list[Any]:
    """Seaborn's histogram and density over the shared bins, then the dots and median."""
    values = np.asarray(da.values, dtype=float).ravel()
    values = values[np.isfinite(values)]
    if values.size == 0:
        return []
    bars = _sns_artists(
        ax,
        lambda: sns.histplot(
            x=values,
            ax=ax,
            bins=ctx.extra["edges"],
            color=_colour(0),
            kde=bool(values.size >= _MIN_KDE_SAMPLES and values.std() > 0),
        ),
    )
    del std, layout
    return bars + _hist_marks(ax, values, ctx.extra["tallest"])


# ---------------------------------------------------------------- chart table


def _distribution_match(cats: VarRange | None = None) -> PlotFilter:
    # The holoviews distribution twins: no float inputs, any cats, repeats to show.
    return PlotFilter(
        float_range=VarRange.exactly(0),
        cat_range=cats if cats is not None else VarRange.unbounded(),
        repeats_range=VarRange.at_least(2),
    )


def _title_vs(var: str, layout: _Layout) -> str:
    return f"{var} vs {layout.x}" if layout.x is not None else var


CHARTS: dict[str, SvgChart | TabularSvgChart] = {}


def _register(*charts: SvgChart | TabularSvgChart) -> None:
    for chart in charts:
        CHARTS[chart.name] = chart


_register(
    SvgChart(
        name="line",
        match=PlotFilter(
            float_range=VarRange.exactly(1),
            repeats_range=VarRange.exactly(1),
            input_range=VarRange.at_least(1),
        ),
        result_types=SCALAR_RESULT_TYPES,
        layout=_layout_line,
        draw=_either(_draw_line, _sns_line),
    ),
    SvgChart(
        name="curve",
        match=PlotFilter(
            float_range=VarRange.exactly(1),
            repeats_range=VarRange.at_least(2),
            input_range=VarRange.at_least(1),
        ),
        result_types=SCALAR_RESULT_TYPES,
        layout=_layout_line,
        draw=_either(_draw_curve, _sns_curve),
    ),
    SvgChart(
        name="heatmap",
        match=PlotFilter(
            float_range=VarRange.at_least(2),
            input_range=VarRange.at_least(2),
        ),
        result_types=(ResultFloat,),
        layout=_layout_heatmap,
        draw=_either(_draw_heatmap, _sns_heatmap),
        figsize=(6.4, 4.8),
        title=lambda var, _layout: f"Heatmap of {var}",
    ),
    SvgChart(
        name="bar",
        match=PlotFilter(
            float_range=VarRange.exactly(0),
            cat_range=VarRange.at_least(1),
            repeats_range=VarRange.exactly(1),
            input_range=VarRange.at_least(1),
        ),
        result_types=(ResultFloat,),
        layout=_layout_bar,
        draw=_either(_draw_bar, _sns_bar),
    ),
    SvgChart(
        name="box_whisker",
        match=_distribution_match(),
        result_types=(ResultFloat,),
        layout=_layout_groups,
        draw=_either(_draw_box_whisker, _sns_box_whisker),
        keep_repeats=True,
        decorate=_decorate_groups,
        title=_title_vs,
    ),
    SvgChart(
        name="histogram",
        # The twin: no inputs at all, so the repeats are the whole distribution.
        match=PlotFilter(float_range=VarRange.exactly(0), input_range=VarRange.exactly(0)),
        result_types=(ResultFloat,),
        layout=_layout_none,
        draw=_either(_draw_histogram, _sns_histogram),
        keep_repeats=True,
        decorate=_decorate_histogram,
        prepare=_hist_scale,
        title=lambda var, _layout: f"Histogram of {var}",
    ),
    SvgChart(
        name="violin",
        match=_distribution_match(),
        result_types=(ResultFloat,),
        layout=_layout_groups,
        draw=_either(_draw_violin, _sns_violin),
        keep_repeats=True,
        decorate=_decorate_groups,
        prepare=_violin_pad,
        title=_title_vs,
        auto=False,
    ),
    SvgChart(
        name="scatter_jitter",
        match=_distribution_match(VarRange.at_most(1)),
        result_types=(ResultFloat,),
        layout=_layout_groups,
        draw=_either(_draw_scatter_jitter, _sns_scatter_jitter),
        keep_repeats=True,
        decorate=_decorate_groups,
        title=_title_vs,
        auto=False,
    ),
    SvgChart(
        name="scatter",
        match=PlotFilter(float_range=VarRange.exactly(0), repeats_range=VarRange.exactly(1)),
        result_types=SCALAR_RESULT_TYPES,
        layout=_layout_groups,
        draw=_either(_draw_scatter, _sns_scatter),
        decorate=_decorate_groups,
        title=_title_vs,
        auto=False,
    ),
    SvgChart(
        name="band",
        match=PlotFilter(repeats_range=VarRange.at_least(1)),
        result_types=SCALAR_RESULT_TYPES,
        layout=_layout_band,
        draw=_either(_draw_band, _sns_band),
        keep_repeats=True,
        framed=False,
        decorate=_decorate_band,
        title=_title_vs,
        auto=False,
    ),
    SvgChart(
        name="volume",
        # The twin's rule: three floats, no cats; repeats reduce to their mean.
        match=PlotFilter(float_range=VarRange.exactly(3), cat_range=VarRange.exactly(0)),
        result_types=(ResultFloat,),
        layout=_layout_volume,
        draw=_draw_volume,
        figsize=(6.4, 4.8),
        decorate=_decorate_volume,
        prepare=_volume_levels,
        title=lambda var, layout: f"{var} vs {layout.x} and {layout.y}",
    ),
    SvgChart(
        name="surface",
        # The twin's rule: two floats, any cats (one panel each), no panel results.
        match=PlotFilter(
            float_range=VarRange.exactly(2),
            cat_range=VarRange.unbounded(),
            panel_range=VarRange.exactly(0),
            repeats_range=VarRange.at_least(1),
            input_range=VarRange.at_least(1),
        ),
        result_types=(ResultFloat,),
        layout=_layout_surface,
        draw=_draw_surface,
        figsize=(6.4, 4.8),
        keep_repeats=True,
        decorate=_decorate_surface,
        title=lambda var, layout: f"{var} vs {layout.x} and {layout.y}",
        auto=False,
        projection="3d",
    ),
    SvgChart(
        name="table",
        match=PlotFilter(),
        result_types=(ResultFloat, ResultBool, ResultString),
        layout=_layout_none,
        draw=_draw_table,
        figsize=_table_figsize,
        framed=False,
        numeric=False,
        decorate=_decorate_table,
        title=lambda var, _layout: var,
        auto=False,
    ),
)


# ---------------------------------------------------------------- rendering


def frame_dims(da: xr.DataArray, layout: _Layout) -> list[str]:
    """The dims of ``da`` a chart with ``layout`` draws as panels or frames, in dataset order."""
    shown = set(layout.shown())
    return [str(d) for d in da.dims if d not in shown and d != _REPEAT]


def _frames(da: xr.DataArray, dims: list[str]) -> tuple[list[dict[str, Any]], int]:
    """The first MAX_SVG_FRAMES index selections over ``dims``, and the full count."""
    sizes = [da.sizes[d] for d in dims]
    total = int(np.prod(sizes)) if sizes else 1
    combos = itertools.islice(itertools.product(*(range(s) for s in sizes)), MAX_SVG_FRAMES)
    return [dict(zip(dims, combo, strict=True)) for combo in combos], total


def _finite_limits(*arrays: np.ndarray) -> tuple[float, float]:
    values = np.concatenate([np.asarray(a, dtype=float).ravel() for a in arrays])
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0, 1.0
    lo, hi = float(values.min()), float(values.max())
    if lo == hi:
        lo, hi = lo - 0.5, hi + 0.5
    return lo, hi


def render_svg(
    chart: SvgChart,
    da: xr.DataArray,
    layout: _Layout,
    *,
    title: str = "",
    svg_layout: str = "auto",
    svg_style: str = "seaborn-ticks",
) -> str:
    """Draw ``da`` as one SVG: a static chart, or one panel or frame per frame-dim combination.

    Args:
        chart: The chart type to draw.
        da: The result variable, with ``repeat`` (reduced by mean here unless the chart
            keeps repeats) and any frame dims.
        layout: Which dims the chart shows; every other non-repeat dim is a frame dim.
        title: The axes title.
        svg_layout: How to show the frame dims: ``"grid"`` (small multiples),
            ``"frames"`` (an animation) or ``"auto"`` (a grid up to MAX_SVG_PANELS).
        svg_style: The look, one of ``SVG_STYLES`` (``"plain"`` without seaborn).

    Returns:
        str: A standalone SVG document with no script and no external reference.
    """
    std = None
    if not chart.numeric:
        data = da
    else:
        da = da.astype(float)
        if chart.keep_repeats or _REPEAT not in da.dims:
            data = da
        else:
            data = da.mean(_REPEAT)
            std = da.std(_REPEAT).fillna(0.0)
    if not chart.numeric:
        lo, hi = 0.0, 1.0
    elif chart.name == "curve" and std is not None:
        lo, hi = _finite_limits(data.values - std.values, data.values + std.values)
    else:
        lo, hi = _finite_limits(data.values)
    hue_values = tuple(data[layout.hue].values) if layout.hue is not None else ()
    ctx = _Ctx(
        lo=lo,
        hi=hi,
        hue_values=hue_values,
        ylabel=str(da.attrs.get("label", "")),
        extra=chart.prepare(data, layout) if chart.prepare is not None else {},
    )
    dims = frame_dims(data, layout) if chart.framed else []
    decorate = chart.decorate or _decorate

    def draw(ax: Axes, sel: dict[str, int]) -> list[Any]:
        frame = data.isel(sel) if sel else data
        frame_std = None if std is None else (std.isel(sel) if sel else std)
        return chart.draw(ax, frame, frame_std, layout, ctx)

    figsize = chart.figsize(data) if callable(chart.figsize) else chart.figsize
    return _draw_frames(
        name=f"svg {chart.name} of {da.name}",
        salt=f"bencher-{chart.name}-{da.name}",
        figsize=figsize,
        source=data,
        dims=dims,
        decorate=lambda fig, ax: decorate(fig, ax, chart, data, layout, ctx, title),
        draw=draw,
        finish=_legend_band if chart.name == "band" else None,
        svg_layout=svg_layout,
        projection=chart.projection,
        svg_style=svg_style,
    )


def _use_grid(svg_layout: str, total: int) -> bool:
    """Whether ``total`` frame-dim combinations draw as a grid of panels, not frames."""
    if svg_layout not in SVG_LAYOUTS:
        raise ValueError(f"svg_layout must be one of {SVG_LAYOUTS}, not {svg_layout!r}")
    if total <= 1 or svg_layout == "frames":
        return False
    return svg_layout == "grid" or total <= MAX_SVG_PANELS


def _draw_frames(
    *,
    name: str,
    salt: str,
    figsize: tuple[float, float],
    source: xr.DataArray,
    dims: list[str],
    decorate: Callable[[Figure, Axes], None],
    draw: Callable[[Axes, dict[str, int]], list[Any]],
    finish: Callable[[Axes], None] | None = None,
    svg_layout: str = "auto",
    projection: str | None = None,
    svg_style: str = "seaborn-ticks",
) -> str:
    """The machinery every chart shares: one panel or frame per ``dims`` combination.

    ``source`` gives the frame dims' sizes and the values each panel title or frame label
    names; ``decorate`` draws what is fixed across frames and ``draw`` one frame's
    artists. ``finish`` runs after the last frame (a legend over the frame artists).
    ``svg_layout`` picks a grid of panels or an animation (see :func:`_use_grid`), and
    ``svg_style`` the look (see ``SVG_STYLES``), active only while this chart draws.
    """
    frames, total = _frames(source, dims)
    if total > MAX_SVG_FRAMES:
        log.warning(
            "%s: %d frames over %s; drawing the first %d", name, total, dims, MAX_SVG_FRAMES
        )
    style = _resolve_style(svg_style)
    rc = {
        "svg.fonttype": "none",
        "svg.hashsalt": salt,
        "font.family": "sans-serif",
        "font.size": 9,
        **style.rc,
    }
    subplot_kw = {"projection": projection} if projection is not None else {}
    grid = _use_grid(svg_layout, total)
    if style.despine and projection is None:
        decorate = _despined(decorate, style)
    token = _STYLE.set(style)
    try:
        svg = _draw_figure(
            rc, grid, figsize, source, frames, total, decorate, draw, finish, subplot_kw
        )
    finally:
        _STYLE.reset(token)
    if grid:
        return _walk_panels(_finish(svg), len(frames))
    return _animate(svg, len(frames)) if len(frames) > 1 else _finish(svg)


def _despined(
    decorate: Callable[[Figure, Axes], None], style: _Style
) -> Callable[[Figure, Axes], None]:
    """``decorate``, then seaborn's despine: no top or right spine, the others set off."""

    def run(fig: Figure, ax: Axes) -> None:
        decorate(fig, ax)
        if style.sns is not None and ax.axison:
            style.sns.despine(ax=ax, offset=5)

    return run


def _draw_figure(
    rc: dict[str, Any],
    grid: bool,
    figsize: tuple[float, float],
    source: xr.DataArray,
    frames: list[dict[str, int]],
    total: int,
    decorate: Callable[[Figure, Axes], None],
    draw: Callable[[Axes, dict[str, int]], list[Any]],
    finish: Callable[[Axes], None] | None,
    subplot_kw: dict[str, Any],
) -> str:
    """One chart's figure, drawn in ``rc`` and saved as SVG text (before the animation)."""
    import matplotlib as mpl
    from matplotlib.figure import Figure

    with mpl.rc_context(rc):
        if grid:
            fig = _draw_grid(figsize, source, frames, decorate, draw, subplot_kw)
        else:
            fig = Figure(figsize=figsize)
            animated = len(frames) > 1
            top = 0.9 if animated else 1.0
            fig.set_layout_engine("constrained", rect=(0, 0.04 if animated else 0, 1, top))
            ax = fig.add_subplot(**subplot_kw)
            decorate(fig, ax)
            if animated:
                _progress_track(fig)
            for i, sel in enumerate(frames):
                artists = draw(ax, sel)
                if animated:
                    artists += _frame_overlay(fig, source, sel, i, len(frames))
                for k, artist in enumerate(artists):
                    artist.set_gid(f"{_FRAME_GID}{i}_{k}")
            if finish is not None:
                finish(ax)
        if total > len(frames):
            fig.text(
                0.99,
                _PROGRESS_HEIGHT + 0.004,
                f"first {len(frames)} of {total} {'panels' if grid else 'frames'}",
                ha="right",
                va="bottom",
                fontsize=7,
                color="#b00020",
            )
        buf = io.StringIO()
        fig.savefig(buf, format="svg", metadata={"Date": None, "Creator": "bencher"})
    return buf.getvalue()


def _grid_shape(count: int) -> tuple[int, int]:
    """(rows, columns) for ``count`` panels: 2x2 for four, then rows of three or more."""
    if count in (2, 4):
        cols = 2
    elif count <= _THREE_COLUMN_PANELS:
        cols = 3
    else:
        cols = max(4, math.ceil(math.sqrt(count)))
    return math.ceil(count / cols), cols


def _panel_title(source: xr.DataArray, sel: dict[str, int], wrap: bool = False) -> str:
    """``dim=value`` per dim the panel fixes; with ``wrap``, a line per dim and per value."""
    parts = [f"{d}={_fmt(source[d].values[i])}" for d, i in sel.items()]
    return "\n".join(p.replace("=", "=\n", 1) for p in parts) if wrap else ", ".join(parts)


def _draw_grid(
    figsize: tuple[float, float],
    source: xr.DataArray,
    frames: list[dict[str, int]],
    decorate: Callable[[Figure, Axes], None],
    draw: Callable[[Axes, dict[str, int]], list[Any]],
    subplot_kw: dict[str, Any],
) -> Figure:
    """Small multiples: one panel per frame, all decorated alike, sharing the furniture.

    The figure gets one title, one legend and one colour bar. Flat panels share one label
    per axis; 3D panels keep their own axis labels.

    The figure keeps the chart's width, so text keeps its size at a fixed display width;
    the panels share it. Each panel's axes group gets an id the walking highlight
    animates (see :func:`_walk_panels`), and a border that lights on its turn.
    """
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle

    style = _style()
    rows, cols = _grid_shape(len(frames))
    width, height = figsize
    panel_h = float(np.clip(width / cols * height / width * 1.25, 1.5, height))
    fig = Figure(figsize=(width, rows * panel_h + 0.9))
    fig.set_layout_engine("constrained")
    grid = fig.subplots(rows, cols, squeeze=False, subplot_kw=subplot_kw)
    panels = list(grid.ravel()[: len(frames)])
    for spare in grid.ravel()[len(frames) :]:
        spare.remove()
    setattr(fig, _PANELS_ATTR, panels)
    for ax in panels:
        decorate(fig, ax)
    first = panels[0]
    fig.suptitle(first.get_title())
    flat = subplot_kw.get("projection") is None
    if flat:
        if first.get_xlabel():
            fig.supxlabel(first.get_xlabel(), fontsize=style.font)
        if first.get_ylabel():
            fig.supylabel(first.get_ylabel(), fontsize=style.font)
    legend = first.get_legend()
    if legend is not None:
        fig.legend(
            handles=legend.legend_handles,
            labels=[t.get_text() for t in legend.get_texts()],
            title=legend.get_title().get_text() or None,
            loc="outside right upper",
            fontsize=style.font,
            title_fontsize=style.font,
        )
    # The characters that fit across one panel: the axes get about 0.8 of the figure
    # width (the rest is labels, colour bar and gaps), and a glyph about 0.6 em.
    title_chars = int(0.8 * width * 72 / cols / (style.font * 0.6))
    # One title too wide for its panel wraps every title, so the panels stay alike.
    wrap = max(len(_panel_title(source, sel)) for sel in frames) > title_chars
    for i, (ax, sel) in enumerate(zip(panels, frames, strict=True)):
        draw(ax, sel)
        ax.set_title(_panel_title(source, sel, wrap), fontsize=style.font)
        if ax.get_legend() is not None:
            ax.get_legend().remove()
        if flat:
            ax.set_xlabel("")
            ax.set_ylabel("")
            # Shared limits: only the panels with none below keep x tick labels, and only
            # the first column keeps y tick labels.
            inner = []
            if i + cols < len(panels):
                ax.tick_params(labelbottom=False)
                inner.append("bottom")
            if i % cols:
                ax.tick_params(labelleft=False)
                inner.append("left")
            if style.despine:
                _flush_inner_edges(ax, inner)
            _thin_fixed_ticks(ax.xaxis, max(2, _MAX_TICKS // cols), title_chars)
            _thin_fixed_ticks(ax.yaxis, max(3, _MAX_TICKS // rows))
        ax.set_gid(f"{_PANEL_GID}{i}")
        glow = Rectangle(
            (0, 0),
            1,
            1,
            transform=ax.transAxes,
            fill=False,
            edgecolor=style.accent,
            lw=2.5,
            clip_on=False,
            zorder=10,
        )
        glow.set_gid(f"{_GLOW_GID}{i}")
        # On the figure, not the axes: 3D axes draw only 3D artists.
        fig.add_artist(glow)
    return fig


def _flush_inner_edges(ax: Axes, edges: list[str]) -> None:
    """Pull a despined panel's inner ``edges`` (the ones a neighbour labels) back flush.

    Despine sets every spine 5 pt out. On an edge with no tick labels that leaves bare tick
    marks on a detached line, so the edge keeps its spine, at the axes, with no ticks.
    """
    for edge in edges:
        ax.spines[edge].set_position(("outward", 0))
        ax.tick_params(**{edge: False})


def _thin_fixed_ticks(axis: Any, limit: int, max_chars: int = 0) -> None:
    """Keep at most ``limit`` of an axis's fixed (categorical) ticks, evenly spaced, ends kept.

    A panel is a fraction of the chart's width, so the labels a full chart fits overlap.
    With ``max_chars``, the kept labels, a space apart, also fit in that many characters.
    """
    from matplotlib.ticker import FixedLocator

    locator = axis.get_major_locator()
    if not isinstance(locator, FixedLocator) or not len(locator.locs):
        return
    locs = list(locator.locs)
    labels = axis.get_major_formatter().format_ticks(locs)
    if max_chars:
        widest = max(len(label) for label in labels) + 1
        limit = max(2, min(limit, max_chars // widest))
    if len(locs) <= limit:
        return
    # Evenly spaced, first and last kept, so the labels span the whole axis.
    keep = sorted({int(i) for i in np.linspace(0, len(locs) - 1, limit).round()})
    axis.set_ticks([locs[i] for i in keep], [labels[i] for i in keep])


def _walk_panels(svg: str, count: int) -> str:
    """Add the CSS that walks a highlight over ``count`` panels, in sweep order, looping.

    Each panel's turn lasts PANEL_SECONDS: its border lights and every other panel dims a
    little. No mark moves, so every instant is the whole chart. The animation sits in a
    ``prefers-reduced-motion: no-preference`` block, so a reader who asks for less motion
    (and any renderer without CSS animation) sees every panel at full strength, unlit.
    """
    cycle = count * PANEL_SECONDS
    lit = (PANEL_SECONDS - _PANEL_FADE) / cycle * 100
    off = PANEL_SECONDS / cycle * 100
    back = (cycle - _PANEL_FADE) / cycle * 100

    def keyframes(name: str, on: float, rest: float) -> str:
        return (
            f"@keyframes {name}{{0%,{lit:.4g}%{{opacity:{on:g}}}"
            f"{off:.4g}%,{back:.4g}%{{opacity:{rest:g}}}100%{{opacity:{on:g}}}}}"
        )

    rules = []
    for i in range(count):
        # A negative delay starts panel i's cycle already running, its turn at i steps.
        delay = f"{i * PANEL_SECONDS - cycle:g}s" if i else "0s"
        timing = f"{cycle:g}s ease-in-out {delay} infinite"
        rules.append(f"#{_PANEL_GID}{i}{{animation:bnwalk {timing}}}")
        rules.append(f"#{_GLOW_GID}{i}{{animation:bnlight {timing}}}")
    style = (
        "<style>"
        f"[id^={_GLOW_GID}]{{opacity:0}}"
        "@media (prefers-reduced-motion:no-preference){"
        f"{keyframes('bnwalk', 1, _PANEL_DIM)}{keyframes('bnlight', 1, 0)}{''.join(rules)}"
        "}</style>"
    )
    head = svg.index(">", svg.index("<svg")) + 1
    return f"{svg[:head]}\n{style}{svg[head:]}"


def _colorbar(fig: Figure, ax: Axes, mappable: Any, label: str) -> None:
    """A colour bar for ``ax``, or one bar for every panel of a grid (drawn once)."""
    panels = getattr(fig, _PANELS_ATTR, None)
    if panels is None:
        fig.colorbar(mappable, ax=ax, label=label)
    elif ax is panels[0]:
        rows, _cols = _grid_shape(len(panels))
        # As thick as a single chart's bar, however many rows it spans.
        fig.colorbar(mappable, ax=panels, label=label, aspect=20 * rows)


def _decorate(
    fig: Figure,
    ax: Axes,
    chart: SvgChart,
    mean: xr.DataArray,
    layout: _Layout,
    ctx: _Ctx,
    title: str,
) -> None:
    """Draw everything fixed across frames: axes, limits, ticks, legend, colour bar."""
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    x_dim = layout.x_dim()
    ax.set_title(title)
    ax.set_xlabel(x_dim)
    ax.autoscale(False)
    xs = mean[x_dim].values
    margin = (ctx.hi - ctx.lo) * 0.05
    if chart.name in ("line", "curve"):
        # xs.min()/max() keep the dtype, so a datetime64 axis (a time-typed input) works;
        # one numeric sample gets a unit span around it.
        if xs.size > 1:
            ax.set_xlim(xs.min(), xs.max())
        elif np.issubdtype(xs.dtype, np.number):
            ax.set_xlim(float(xs[0]) - 0.5, float(xs[0]) + 0.5)
        ax.set_ylim(ctx.lo - margin, ctx.hi + margin)
        ax.set_ylabel(ctx.ylabel or str(mean.name))
        _grid(ax)
    elif chart.name == "bar":
        ax.set_xlim(-0.5, len(xs) - 0.5)
        ax.set_ylim(min(0.0, ctx.lo - margin), max(0.0, ctx.hi + margin))
        _categorical_ticks(ax.set_xticks, [_fmt(v) for v in xs])
        ax.set_ylabel(ctx.ylabel or str(mean.name))
        _grid(ax, "y")
    else:
        y = layout.y_dim()
        ys = mean[y].values
        ax.set_xlim(-0.5, len(xs) - 0.5)
        ax.set_ylim(-0.5, len(ys) - 0.5)
        ax.set_ylabel(y)
        _categorical_ticks(ax.set_xticks, [_fmt(v) for v in xs])
        _categorical_ticks(ax.set_yticks, [_fmt(v) for v in ys])
        mappable = ScalarMappable(norm=Normalize(ctx.lo, ctx.hi), cmap=_style().heat_cmap)
        _colorbar(fig, ax, mappable, ctx.ylabel or str(mean.name))
    if layout.hue is not None:
        colours = [_colour(i, len(ctx.hue_values)) for i in range(len(ctx.hue_values))]
        labels = [_fmt(v) for v in ctx.hue_values]
        if chart.name == "bar":
            handles = [Patch(color=c, label=t) for c, t in zip(colours, labels, strict=True)]
        else:
            handles = [
                Line2D([], [], color=c, label=t) for c, t in zip(colours, labels, strict=True)
            ]
        font = _style().hue_legend_font
        ax.legend(handles=handles, title=layout.hue, fontsize=font, title_fontsize=font)


_PROGRESS_HEIGHT = 0.012


def _progress_track(fig: Figure) -> None:
    """The static grey track the per-frame progress bar fills."""
    from matplotlib.patches import Rectangle

    track = Rectangle((0.0, 0.0), 1.0, _PROGRESS_HEIGHT, transform=fig.transFigure, color="#dddddd")
    fig.add_artist(track)


def _frame_overlay(
    fig: Figure, mean: xr.DataArray, sel: dict[str, int], index: int, count: int
) -> list[Any]:
    """The per-frame label naming the frame-dim values, and the filled progress bar."""
    from matplotlib.patches import Rectangle

    label = ", ".join(f"{d} = {_fmt(mean[d].values[i])}" for d, i in sel.items())
    text = fig.text(
        0.5,
        0.95,
        f"{label}   ({index + 1}/{count})",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
    )
    bar = Rectangle(
        (0.0, 0.0),
        (index + 1) / count,
        _PROGRESS_HEIGHT,
        transform=fig.transFigure,
        color="#4c72b0",
    )
    fig.add_artist(bar)
    return [text, bar]


# A frame artist's opening tag: matplotlib puts the gid on a wrapping <g> for most
# artists but on the element itself for an image (a self-closing <image .../>).
_FRAME_ELEMENT = re.compile(rf'<(\w+)([^>]*? id="{_FRAME_GID}(\d+)_\d+"[^>]*?)(/?)>')
_FONT_FAMILY = re.compile(r"font-family: *[^;\"]+")
# The XML prolog, the DOCTYPE (which names an external DTD) and matplotlib's RDF
# metadata block: none of them draws anything, and the SVG pane wants <svg> first.
_PREAMBLE = re.compile(r"\A.*?(?=<svg)", re.DOTALL)
_METADATA = re.compile(r"\s*<metadata>.*?</metadata>", re.DOTALL)


def _finish(svg: str) -> str:
    """Strip the preamble and name a generic font stack, so the SVG names no font file."""
    svg = _PREAMBLE.sub("", svg, count=1)
    svg = _METADATA.sub("", svg, count=1)
    return _FONT_FAMILY.sub(f"font-family: {_FONT_STACK}", svg)


def _animate(svg: str, count: int) -> str:
    """Show frame 0 by default and cycle every frame group with discrete SMIL opacity."""
    key_times = ";".join(f"{i / count:.6g}" for i in range(count))
    duration = f"{count * FRAME_SECONDS:g}s"

    def repl(m: re.Match) -> str:
        tag, attrs, index, self_closing = m.groups()
        i = int(index)
        values = ";".join("1" if j == i else "0" for j in range(count))
        animate = (
            f'<animate attributeName="opacity" values="{values}" keyTimes="{key_times}" '
            f'dur="{duration}" calcMode="discrete" repeatCount="indefinite"/>'
        )
        opened = f'<{tag}{attrs} opacity="{1 if i == 0 else 0}">{animate}'
        return f"{opened}</{tag}>" if self_closing else opened

    return _finish(_FRAME_ELEMENT.sub(repl, svg))


# ---------------------------------------------------------------- tabular charts


@dataclass(frozen=True)
class _TabPlan:
    """What a tabular chart resolved once for every frame: columns, limits, scales."""

    spec: Any
    x: Any = None
    ys: tuple = ()
    xlim: tuple | None = None
    ylim: tuple | None = None
    clim: tuple[float, float] | None = None
    edges: np.ndarray | None = None
    xlabel: str = ""
    ylabel: str = ""
    title: str = ""


@dataclass(frozen=True)
class TabularSvgChart:
    """One svg chart that draws the table a ``ResultDataSet`` sample holds.

    The twin draws one plot per sample; this draws one frame per sample, so the frame
    machinery covers every swept dim (``repeat`` included). ``spec_cls`` is the
    twin's column spec (``XYScatter``...): its fields are the options this chart takes,
    from the result var's declared ``container=`` spec or the render keywords, and its
    helpers resolve the columns the same way. ``plan`` resolves columns and limits over
    every frame's table, ``draw`` draws one.
    """

    name: str
    spec_cls: Callable[[], type]
    plan: Callable[[Any, list[pd.DataFrame]], _TabPlan]
    draw: Callable[[Axes, pd.DataFrame, _TabPlan], list[Any]]
    match: PlotFilter = field(default_factory=lambda: PlotFilter(panel_range=VarRange.at_least(1)))
    result_types: tuple[type, ...] = (ResultDataSet,)
    figsize: tuple[float, float] = (6.4, 4.8)
    auto: bool = False


def _column_limits(columns: list[pd.Series]) -> tuple:
    """Fixed axis limits over one column of every frame, with a 5% margin for numbers."""
    import pandas as pd

    joined = pd.concat(columns, ignore_index=True)
    if pd.api.types.is_datetime64_any_dtype(joined):
        joined = joined.dropna()
        return (joined.min(), joined.max()) if len(joined) else (None, None)
    lo, hi = _finite_limits(pd.to_numeric(joined).to_numpy(dtype=float, na_value=np.nan))
    margin = (hi - lo) * 0.05
    return lo - margin, hi + margin


def _label(spec: Any, role: str, default: str) -> str:
    value = getattr(spec, role, None)
    return str(value) if value is not None else default


def _plan_xy(spec: Any, frames: list[pd.DataFrame], *, curve: bool = False) -> _TabPlan:
    first = frames[0]
    if curve:
        x, ys = spec._resolve_columns(first)  # noqa: SLF001 - the twin's own resolution
    else:
        x, y = spec.axes(first, spec.x, spec.y)
        ys = [y]
    for df in frames[1:]:
        for col in (x, *ys):
            spec.check(df, col, "column")
    xlim = _column_limits([df[x] for df in frames])
    ylim = _column_limits([df[col] for df in frames for col in ys])
    clim = None
    colour = getattr(spec, "color", None)
    if colour is not None:
        for df in frames:
            spec.check(df, colour, "color")
        clim = _finite_limits(*(df[colour].to_numpy(dtype=float) for df in frames))
    y_default = str(ys[0]) if len(ys) == 1 else ""
    return _TabPlan(
        spec=spec,
        x=x,
        ys=tuple(ys),
        xlim=xlim,
        ylim=ylim,
        clim=clim,
        xlabel=_label(spec, "xlabel", str(x)),
        ylabel=_label(spec, "ylabel", y_default),
        title=_label(spec, "title", f"{y_default or ', '.join(map(str, ys))} vs {x}"),
    )


def _plan_curve(spec: Any, frames: list[pd.DataFrame]) -> _TabPlan:
    return _plan_xy(spec, frames, curve=True)


def _plan_histogram(spec: Any, frames: list[pd.DataFrame]) -> _TabPlan:
    cols = spec.columns(frames[0], spec.column, "column")
    for df in frames[1:]:
        for col in cols:
            spec.check(df, col, "column")
    values = [df[c].to_numpy(dtype=float, na_value=np.nan) for df in frames for c in cols]
    lo, hi = spec.bin_range if spec.bin_range is not None else _finite_limits(*values)
    edges = np.linspace(lo, hi, int(spec.bins) + 1)
    tallest = 0.0
    for v in values:
        counts, _ = np.histogram(v[np.isfinite(v)], edges, density=bool(spec.density))
        tallest = max(tallest, float(np.nan_to_num(counts).max(initial=0)))
    tallest = tallest or 1.0
    names = ", ".join(map(str, cols))
    return _TabPlan(
        spec=spec,
        ys=tuple(cols),
        xlim=(edges[0], edges[-1]),
        ylim=(-tallest * 0.15, tallest * 1.1),
        edges=edges,
        xlabel=_label(spec, "xlabel", str(cols[0]) if len(cols) == 1 else ""),
        ylabel=_label(spec, "ylabel", "density" if spec.density else "count"),
        title=_label(spec, "title", f"Histogram of {names}"),
    )


def _plan_hexbin(spec: Any, frames: list[pd.DataFrame]) -> _TabPlan:
    from matplotlib.figure import Figure

    plan = _plan_xy(spec, frames)
    # The tallest hexagon over every frame, from a throwaway figure, so every frame
    # shares one colour scale.
    scratch = Figure().add_subplot()
    tallest = 1.0
    for df in frames:
        cells = _hexbin(scratch, df, plan)
        counts = cells.get_array()
        if counts is not None and counts.size:
            tallest = max(tallest, float(np.max(counts)))
    return dataclasses.replace(plan, clim=(0.0, tallest))


def _xy_arrays(df: pd.DataFrame, x: Any, y: Any) -> tuple[np.ndarray, np.ndarray]:
    return df[x].to_numpy(), df[y].to_numpy()


def _hexbin(ax: Axes, df: pd.DataFrame, plan: _TabPlan, **kwargs: Any) -> Any:
    xs, ys = _xy_arrays(df, plan.x, plan.ys[0])
    extent = (*(plan.xlim or (0, 1)), *(plan.ylim or (0, 1)))
    return ax.hexbin(
        xs.astype(float),
        ys.astype(float),
        gridsize=int(plan.spec.gridsize),
        extent=extent,
        mincnt=plan.spec.min_count if plan.spec.min_count is not None else 1,
        cmap=plan.spec.cmap,
        linewidths=0,
        **kwargs,
    )


def _draw_xy_scatter(ax: Axes, df: pd.DataFrame, plan: _TabPlan) -> list[Any]:
    xs, ys = _xy_arrays(df, plan.x, plan.ys[0])
    colour = plan.spec.color
    if colour is not None and plan.clim is not None:
        return [
            ax.scatter(
                xs,
                ys,
                c=df[colour].to_numpy(dtype=float),
                cmap=plan.spec.cmap,
                vmin=plan.clim[0],
                vmax=plan.clim[1],
                s=plan.spec.size * 3,
                linewidths=0,
            )
        ]
    return [ax.scatter(xs, ys, s=plan.spec.size * 3, color=_colour(0), alpha=0.75, linewidths=0)]


def _draw_xy_curve(ax: Axes, df: pd.DataFrame, plan: _TabPlan) -> list[Any]:
    if plan.spec.sort:
        df = df.sort_values(plan.x, kind="stable")
    artists: list[Any] = []
    for i, col in enumerate(plan.ys):
        marker = "o" if plan.spec.markers else None
        artists += ax.plot(
            df[plan.x].to_numpy(),
            df[col].to_numpy(),
            color=_colour(i, len(plan.ys)),
            marker=marker,
            ms=plan.spec.size * 0.6,
            lw=2,
        )
    return artists


def _draw_xy_histogram(ax: Axes, df: pd.DataFrame, plan: _TabPlan) -> list[Any]:
    edges = plan.edges
    if edges is None:
        return []
    alpha = 0.55 if len(plan.ys) > 1 else 0.8
    top = (plan.ylim or (0, 1))[1]
    artists: list[Any] = []
    for i, col in enumerate(plan.ys):
        values = df[col].to_numpy(dtype=float, na_value=np.nan)
        values = values[np.isfinite(values)]
        counts, _ = np.histogram(values, edges, density=bool(plan.spec.density))
        artists.append(
            ax.stairs(counts, edges, fill=True, color=_colour(i, len(plan.ys)), alpha=alpha)
        )
        if values.size:
            median = float(np.median(values))
            artists.append(
                ax.vlines(median, 0, top / 1.1, colors=_colour(i, len(plan.ys)), lw=3, zorder=4)
            )
    return artists


def _draw_xy_hexbin(ax: Axes, df: pd.DataFrame, plan: _TabPlan) -> list[Any]:
    clim = plan.clim or (0.0, 1.0)
    return [_hexbin(ax, df, plan, vmin=clim[0], vmax=clim[1])]


def _decorate_tabular(fig: Figure, ax: Axes, chart: TabularSvgChart, plan: _TabPlan) -> None:
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    ax.set_title(plan.title)
    ax.autoscale(False)
    if plan.xlim is not None and None not in plan.xlim:
        ax.set_xlim(*plan.xlim)
    if plan.ylim is not None and None not in plan.ylim:
        ax.set_ylim(*plan.ylim)
    ax.set_xlabel(plan.xlabel)
    ax.set_ylabel(plan.ylabel)
    _grid(ax)
    if getattr(plan.spec, "data_aspect", None) is not None:
        ax.set_aspect(float(plan.spec.data_aspect), adjustable="box")
    if plan.clim is not None:
        label = "count" if chart.name == "xy_hexbin" else str(plan.spec.color)
        mappable = ScalarMappable(norm=Normalize(*plan.clim), cmap=plan.spec.cmap)
        _colorbar(fig, ax, mappable, label)
    if len(plan.ys) > 1:
        names = [str(c) for c in plan.ys]
        k = len(names)
        if chart.name == "xy_histogram":
            handles = [Patch(color=_colour(i, k), label=n) for i, n in enumerate(names)]
        else:
            handles = [Line2D([], [], color=_colour(i, k), label=n) for i, n in enumerate(names)]
        ax.legend(handles=handles, fontsize=_style().font)


def _spec_classes() -> dict[str, type]:
    from bencher.results.holoview_results.xy_curve_result import XYCurve
    from bencher.results.holoview_results.xy_hexbin_result import XYHexbin
    from bencher.results.holoview_results.xy_histogram_result import XYHistogram
    from bencher.results.holoview_results.xy_scatter_result import XYScatter

    return {
        "xy_scatter": XYScatter,
        "xy_curve": XYCurve,
        "xy_histogram": XYHistogram,
        "xy_hexbin": XYHexbin,
    }


_register(
    TabularSvgChart(
        name="xy_scatter",
        spec_cls=lambda: _spec_classes()["xy_scatter"],
        plan=_plan_xy,
        draw=_draw_xy_scatter,
    ),
    TabularSvgChart(
        name="xy_curve",
        spec_cls=lambda: _spec_classes()["xy_curve"],
        plan=_plan_curve,
        draw=_draw_xy_curve,
        figsize=(6.4, 4.0),
    ),
    TabularSvgChart(
        name="xy_histogram",
        spec_cls=lambda: _spec_classes()["xy_histogram"],
        plan=_plan_histogram,
        draw=_draw_xy_histogram,
        figsize=(6.4, 4.0),
    ),
    TabularSvgChart(
        name="xy_hexbin",
        spec_cls=lambda: _spec_classes()["xy_hexbin"],
        plan=_plan_hexbin,
        draw=_draw_xy_hexbin,
    ),
)

# Options that name columns: a list from the caller becomes the tuple the spec holds.
_COLUMN_OPTIONS = ("y", "column", "vdims")


def _resolve_spec(chart: TabularSvgChart, rv: Any, options: Mapping[str, Any]) -> Any:
    """The twin's spec for ``rv``: its declared ``container=`` spec, then ``options``."""
    spec_cls = chart.spec_cls()
    names = {f.name for f in dataclasses.fields(spec_cls)} - {"opts"}
    declared = getattr(rv, "container", None)
    values = {n: getattr(declared, n) for n in names} if isinstance(declared, spec_cls) else {}
    for key, value in options.items():
        if key in names and value is not None:
            values[key] = (
                tuple(value) if key in _COLUMN_OPTIONS and isinstance(value, list) else value
            )
    return spec_cls(**values)


def _tabular_svgs(
    chart: TabularSvgChart,
    dataset: xr.Dataset,
    result_vars: tuple | list,
    loader: SampleLoader | None,
    options: Mapping[str, Any],
    svg_layout: str = "auto",
    svg_style: str = "seaborn-ticks",
) -> dict[str, str]:
    from bencher.results.holoview_results.tabular_spec import to_dataframe

    if loader is None:
        return {}
    out: dict[str, str] = {}
    for rv in result_vars:
        if not isinstance(rv, chart.result_types) or rv.name not in dataset:
            continue
        da = dataset[rv.name]
        # The twin squeezes to one value per sample; every dim left is a frame dim.
        da = da.squeeze([d for d in da.dims if da.sizes[d] == 1], drop=False)
        dims = [str(d) for d in da.dims]
        frames, _total = _frames(da, dims)
        tables: list[pd.DataFrame | None] = []
        for sel in frames:
            cell = da.isel(sel) if sel else da
            payload = loader(cell.values.item(), rv)
            try:
                tables.append(to_dataframe(payload, chart.name) if payload is not None else None)
            except TypeError:  # a placeholder pane or a payload that is not a table
                tables.append(None)
        present = [t for t in tables if t is not None]
        if not present:
            continue
        try:
            plan = chart.plan(_resolve_spec(chart, rv, options), present)
        except (ValueError, TypeError) as exc:
            log.warning("svg %s of %s: %s; using the holoviews chart", chart.name, rv.name, exc)
            continue

        def draw(
            ax: Axes,
            sel: dict[str, int],
            _plan: _TabPlan = plan,
            _tables: list = tables,
            _frames: list = frames,
        ) -> list[Any]:
            table = _tables[_frames.index(sel)] if sel else _tables[0]
            return chart.draw(ax, table, _plan) if table is not None else []

        out[rv.name] = _draw_frames(
            name=f"svg {chart.name} of {rv.name}",
            salt=f"bencher-{chart.name}-{rv.name}",
            figsize=chart.figsize,
            source=da,
            dims=dims,
            decorate=lambda fig, ax, _plan=plan: _decorate_tabular(fig, ax, chart, _plan),
            draw=draw,
            svg_layout=svg_layout,
            svg_style=svg_style,
        )
    return out


# ---------------------------------------------------------------- BenchData entry points


def chart_svgs(
    chart: SvgChart | TabularSvgChart,
    dataset: xr.Dataset,
    result_vars: tuple | list,
    cfg: PltCntCfg | None,
    *,
    loader: SampleLoader | None = None,
    options: Mapping[str, Any] | None = None,
    svg_layout: str = "auto",
    svg_style: str = "seaborn-ticks",
) -> dict[str, str]:
    """Every SVG ``chart`` draws for a sweep, keyed by result var name.

    Empty when the sweep shape (``cfg``) is outside ``chart.match`` or no result var has
    a type the chart draws. ``loader`` reads a stored ``ResultDataSet`` sample (the
    tabular charts need it); ``options`` are the twin's chart options (``x=``, ``y=``,
    ``bins=``...), which only the tabular charts take. ``svg_layout`` shows the dims a
    chart does not put on an axis as a grid of panels or as frames (``"auto"``: a grid up
    to MAX_SVG_PANELS panels); ``svg_style`` is the look (see ``SVG_STYLES``).
    """
    if cfg is None or not chart.match.matches_result(cfg, chart.name, override=False).overall:
        return {}
    if isinstance(chart, TabularSvgChart):
        return _tabular_svgs(
            chart, dataset, result_vars, loader, options or {}, svg_layout, svg_style
        )
    floats = [v.name for v in cfg.float_vars]
    cats = [v.name for v in cfg.cat_vars]
    out: dict[str, str] = {}
    for rv in result_vars:
        if not isinstance(rv, chart.result_types) or rv.name not in dataset:
            continue
        da = dataset[rv.name].copy()
        layout = chart.layout(floats, cats, da)
        if layout is None:
            continue
        da.attrs["label"] = label_with_units(rv)
        title = (
            chart.title(rv.name, layout) if chart.title is not None else f"{rv.name} vs {layout.x}"
        )
        out[rv.name] = render_svg(
            chart, da, layout, title=title, svg_layout=svg_layout, svg_style=svg_style
        )
    return out


def svg_pane(svg: str) -> pn.pane.SVG:
    """A Panel pane for one svg-backend chart."""
    return pn.pane.SVG(svg, sizing_mode="fixed")


def _identity(obj: Any) -> Any:
    return obj


def sample_loader(result: Any) -> SampleLoader:
    """Read one stored ``ResultDataSet`` cell of ``result`` as its raw payload."""

    def load(value: Any, result_var: Any) -> Any:
        return result._dataset_sample_to_container(value, result_var, container=_identity)  # noqa: SLF001

    return load


def _cfg_layout(result: Any) -> str:
    """The ``svg_layout`` of a result's run config, ``"auto"`` without one."""
    cfg = getattr(result, "bench_cfg", None)
    return str(getattr(cfg, "svg_layout", None) or "auto")


def _cfg_style(result: Any) -> str:
    """The ``svg_style`` of a result's run config, ``"seaborn-ticks"`` without one."""
    cfg = getattr(result, "bench_cfg", None)
    return str(getattr(cfg, "svg_style", None) or "seaborn-ticks")


@dataclass(frozen=True)
class SvgPlugin:
    """Plot plugin for one svg chart type.

    ``fallback`` is the twin a matching sweep hands over to when no result var is drawable
    here, so selecting svg never loses a plot the default backend would have drawn.
    """

    chart: SvgChart | TabularSvgChart
    priority: int
    fallback: PlotPlugin | None = None
    backend: str = SVG_BACKEND
    requires: frozenset[str] = frozenset({"legacy_result"})

    @property
    def name(self) -> str:
        return self.chart.name

    @property
    def match(self) -> PlotFilter:
        return self.chart.match

    @property
    def auto(self) -> bool:
        return self.chart.auto

    def render(self, data: BenchData) -> pn.viewable.Viewable | None:
        legacy = data.legacy_result
        svgs = chart_svgs(
            self.chart,
            data.dataset,
            data.result_vars,
            data.plt_cnt_cfg,
            loader=sample_loader(legacy) if legacy is not None else None,
            options=data.render_kwargs,
            svg_layout=_cfg_layout(legacy),
            svg_style=_cfg_style(legacy),
        )
        if not svgs:
            return self.fallback.render(data) if self.fallback is not None else None
        return pn.Column(*(svg_pane(s) for s in svgs.values()))


class SvgResult(BenchResultBase):
    """Write a result's svg-backend charts as strings or files, for linking from a PR."""

    def to_svgs(
        self,
        charts: list[str] | None = None,
        svg_layout: str | None = None,
        svg_style: str | None = None,
        **options: Any,
    ) -> dict[str, str]:
        """Every svg-backend chart this sweep draws, keyed ``"<chart>_<result var>"``.

        Args:
            charts: Chart names to draw (see ``bencher.results.svg_result.CHARTS``).
                Defaults to every auto-selected svg chart; ones whose shape rule does not
                match this sweep are skipped. Named-only charts (``violin``, ``table``,
                ``xy_scatter``...) are drawn only when named here.
            svg_layout: How to show the dims a chart does not put on an axis:
                ``"grid"`` (one small panel each, all at once), ``"frames"`` (one
                animation frame each) or ``"auto"`` (a grid up to MAX_SVG_PANELS panels,
                frames past it). Defaults to the run config's ``svg_layout``.
            svg_style: The look: ``"seaborn-ticks"`` (white, ticks, no top or right
                spine), ``"seaborn"`` (darkgrid and the deep palette) or ``"plain"``
                (plain matplotlib). Without seaborn installed every style draws
                ``"plain"``. Defaults to the run config's ``svg_style``.
            **options: The tabular charts' options, as their holoviews twins take them
                (``x=``, ``y=``, ``column=``, ``bins=``...).

        Returns:
            dict[str, str]: Standalone SVG documents.
        """
        names = [n for n, c in CHARTS.items() if c.auto] if charts is None else charts
        unknown = sorted(set(names) - set(CHARTS))
        if unknown:
            raise ValueError(f"Unknown svg charts {unknown}; svg charts are {sorted(CHARTS)}")
        svg_layout = _cfg_layout(self) if svg_layout is None else svg_layout
        if svg_layout not in SVG_LAYOUTS:
            raise ValueError(f"svg_layout must be one of {SVG_LAYOUTS}, not {svg_layout!r}")
        svg_style = _cfg_style(self) if svg_style is None else svg_style
        if svg_style not in SVG_STYLES:
            raise ValueError(f"svg_style must be one of {SVG_STYLES}, not {svg_style!r}")
        result_vars = self.bench_cfg.result_vars
        loader = sample_loader(self)
        out: dict[str, str] = {}
        for name in names:
            svgs = chart_svgs(
                CHARTS[name],
                self.ds,
                result_vars,
                self.plt_cnt_cfg,
                loader=loader,
                options=options,
                svg_layout=svg_layout,
                svg_style=svg_style,
            )
            for var, svg in svgs.items():
                out[f"{name}_{var}"] = svg
        return out

    def to_svg_files(
        self,
        directory: str | Path,
        charts: list[str] | None = None,
        prefix: str = "",
        svg_layout: str | None = None,
        svg_style: str | None = None,
        **options: Any,
    ) -> list[Path]:
        """Write :meth:`to_svgs` to ``directory`` as ``<prefix><chart>_<result var>.svg``.

        To show the files in a GitHub PR or issue, push them with
        :func:`bencher.evidence_ref.push_evidence` and link :func:`bencher.evidence_ref.blob_url`.

        Returns:
            list[Path]: The files written, in chart order.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for key, svg in self.to_svgs(
            charts, svg_layout=svg_layout, svg_style=svg_style, **options
        ).items():
            path = directory / f"{prefix}{key}.svg"
            path.write_text(svg, encoding="utf-8")
            paths.append(path)
        return paths
