"""PR-ready evidence from an A/B comparison: a text-only Markdown block, and PNGs on request.

:func:`~bencher.report_export.compare_results` says *whether* a change moved each
metric. This module shows it: :func:`evidence_markdown` writes the block an agent
pastes as a pull request's ``## Evidence`` section, and :func:`write_evidence_pngs`
draws one chart per metric for local viewing. :func:`write_evidence` writes any of
the comparison JSON, the Markdown and the PNGs in one call; ``bencher compare`` and
``bencher ab`` are its command-line front ends.

The Markdown is text only by default: every chart is text that GitHub draws in the
PR body, with no image and no external resource. ``write_evidence(image_dir=...,
publish_images=...)`` (``bencher ab --images``) also draws an image of each metric
whose image shows more than its text chart and links it above that chart, which
stays. :func:`plan_chart` picks the text form:

- no swept input: a Mermaid ``xychart-beta`` bar per side, or ``diff``-fence text
  bars for a negative value (an xychart bar grows from the axis bottom, not from 0)
  or a spread between repeats as large as the change (printed as ± std);
- one numeric swept input with the same values on both sides: two named xychart
  lines, "before" and "after", which GitHub draws with a legend; with pale ±1 std
  lines when the spread between repeats is as large as the change; ``diff`` bars
  when the values do not print as distinct labels;
- one categorical swept input (string, enum or bool): a table with the change and
  its 95% CI per category;
- two or more swept inputs: an emoji heatmap of the percent change, colored by
  whether it is better or worse for the metric's direction, one table per value of
  a third input when it has few values, else averaged over the rest;
- points or inputs only one side has: a table over the shared points and a note
  of what was left out.

Every metric then gets a caption -- the threshold verdict, the mean change and the
``change`` record of :mod:`bencher.change_stats` -- and a ``<details>`` block with a
CSV of the points its chart shows. With three or more compared metrics, one
``radar-beta`` chart above the per-metric charts shows every metric scaled so the
baseline mean is 1.
"""

from __future__ import annotations

import csv
import html
import io
import json
import math
import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_never

import numpy as np

from bencher.change_stats import (
    DECREASED,
    IMPROVED,
    INCREASED,
    REGRESSED,
    TOO_FEW_SAMPLES,
    unpaired_change,
)
from bencher.claims import Claim, Threshold, Within
from bencher.report_export import _snapshot_ds, compare_results

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    import xarray as xr
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from bencher.bench_cfg import BenchRunCfg
    from bencher.results.bench_result import BenchResult

# xychart-beta labels collide past this many points; longer numeric sweeps are binned.
MAX_CHART_POINTS = 30

# A y axis starts at 0 unless that squeezes the change below this share of the axis.
_MIN_CHANGE_SHARE_FROM_ZERO = 0.05

# Mermaid series colors: readable on GitHub's light and dark themes.
MERMAID_BEFORE_COLOR = "#8c8c8c"
MERMAID_AFTER_COLOR = "#2f81f7"
# The pale ±1 std lines of a BandChart: the series colors at 40% opacity. A lighter
# solid color would be brighter than its mean line on GitHub's dark theme.
MERMAID_BEFORE_BAND_COLOR = f"{MERMAID_BEFORE_COLOR}66"
MERMAID_AFTER_BAND_COLOR = f"{MERMAID_AFTER_COLOR}66"

# The radar needs this many metrics with a usable baseline to be worth drawing.
MIN_RADAR_METRICS = 3

_BEFORE_COLOR = "#8a94a6"
_AFTER_COLOR = "#1f6feb"
_CLAIM_COLOR = "#cf222e"


@dataclass(frozen=True)
class _Profile:
    """One side of one metric, reduced to what a chart draws."""

    swept: tuple[str, ...]  # input dims with more than one value
    x: tuple  # coordinate values of the first swept dim; empty with none swept
    mean: np.ndarray  # one per x (a single value with none swept)
    std: np.ndarray
    samples: int
    points: tuple[np.ndarray, ...]  # the finite samples at each x
    # The mean over repeats at each point of every swept dim (None when built by hand):
    # what a heatmap or an overlap across inputs reads.
    cube: xr.DataArray | None = None


def _finite_samples(da: xr.DataArray) -> np.ndarray:
    values = np.asarray(da.values, dtype=float).ravel()
    return values[np.isfinite(values)]


def _profile(da: xr.DataArray) -> _Profile:
    swept = tuple(d for d in da.dims if d not in ("repeat", "over_time") and da.sizes[d] > 1)
    keep = swept[:1]
    reduce = [d for d in da.dims if d not in keep]
    values = da.astype(float)
    with warnings.catch_warnings():
        # An all-NaN point (never recorded) reduces to NaN; the empty-slice warning is noise.
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = values.mean(dim=reduce, skipna=True)
        std = values.std(dim=reduce, skipna=True)
        cube = values.mean(dim=[d for d in da.dims if d not in swept], skipna=True)
    x = tuple(_plain(v) for v in da[keep[0]].values) if keep else ()
    points = (
        tuple(_finite_samples(values.isel({keep[0]: i})) for i in range(len(x))) if keep else ()
    )
    return _Profile(
        swept=swept,
        x=x,
        mean=np.atleast_1d(np.asarray(mean.values, dtype=float)),
        std=np.atleast_1d(np.nan_to_num(np.asarray(std.values, dtype=float))),
        samples=int(values.notnull().sum()),
        points=points,
        cube=cube,
    )


def _plain(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


# --- chart plans -----------------------------------------------------------------


@dataclass(frozen=True)
class BeforeAfterBars:
    """No swept input: one bar per side."""

    before: float
    after: float


@dataclass(frozen=True)
class SweepChart:
    """One numeric swept input shared by both sides: a "before" line and an "after" line."""

    input_name: str
    labels: tuple[str, ...]
    before: tuple[float, ...]
    after: tuple[float, ...]


@dataclass(frozen=True)
class CategoryRow:
    """One category: its mean on each side and the change between them.

    ``change`` is a :func:`~bencher.change_stats.unpaired_change` record from the
    repeats at that category.
    """

    label: str
    before: float
    after: float
    change: dict


@dataclass(frozen=True)
class CategoryTable:
    """One categorical swept input shared by both sides: a table row per category."""

    input_name: str
    rows: tuple[CategoryRow, ...]


@dataclass(frozen=True)
class BandChart:
    """One numeric swept input whose repeat spread is as large as the change.

    The before and after lines with a pale line at ±1 std of each, so the reader
    sees that the change is inside the noise.
    """

    input_name: str
    labels: tuple[str, ...]
    before: tuple[float, ...]
    after: tuple[float, ...]
    before_std: tuple[float, ...]
    after_std: tuple[float, ...]


@dataclass(frozen=True)
class DiffRow:
    """One point of :class:`DiffBars`; ``label`` is empty with no swept input."""

    label: str
    before: float
    after: float
    before_std: float | None = None  # set when the spread is as large as the change
    after_std: float | None = None


@dataclass(frozen=True)
class DiffBars:
    """Text bars in a ``diff`` fence, red before and green after, grown from 0.

    For what an xychart draws wrong: a negative value with no swept input (an
    xychart bar grows from the axis bottom), a scalar whose spread is as large as
    the change, and swept values that do not print as distinct labels.
    """

    input_name: str | None
    rows: tuple[DiffRow, ...]


@dataclass(frozen=True)
class HeatmapGrid:
    """One table of a :class:`Heatmap`: the means at each (row, column), per side."""

    layer: str | None  # the value of the third swept input, when there is one table per value
    before: tuple[tuple[float, ...], ...]  # [row][column]
    after: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class Heatmap:
    """Two or more swept inputs: a table of the percent change, colored better/worse."""

    row_input: str
    col_input: str
    row_labels: tuple[str, ...]
    col_labels: tuple[str, ...]
    grids: tuple[HeatmapGrid, ...]
    layer_input: str | None
    direction: str
    margin_percent: float
    notes: tuple[str, ...]  # what was averaged, binned or left out


@dataclass(frozen=True)
class OverlapRow:
    label: str
    before: float
    after: float


@dataclass(frozen=True)
class OverlapTable:
    """Points that only one side has: a table over the shared points and what was left out.

    ``input_name`` is None when the sides share no swept input, when neither swept one,
    or when two swept inputs share no point: then there is at most one row, of overall means.
    """

    input_name: str | None
    rows: tuple[OverlapRow, ...]
    left_out: str


@dataclass(frozen=True)
class ImageOnly:
    """Deprecated: evidence is text only, so :func:`plan_chart` never returns this.

    Kept so code that imports or builds it from 1.141.0 and earlier still runs.
    """

    reason: str

    def __post_init__(self) -> None:
        warnings.warn(
            "bencher.evidence.ImageOnly is deprecated: evidence is text only and "
            "plan_chart never returns it.",
            DeprecationWarning,
            stacklevel=3,
        )


ChartPlan = (
    BeforeAfterBars | SweepChart | BandChart | DiffBars | CategoryTable | Heatmap | OverlapTable
)

# Past this many values of a third swept input, a heatmap averages over it instead.
MAX_HEATMAP_TABLES = 6
# Numeric heatmap axes past these sizes are binned like a long sweep.
MAX_HEATMAP_ROWS = 30
MAX_HEATMAP_COLS = 12
# A "Left out" note names at most this many values per reason.
_MAX_NAMED = 8


def _is_number(value: Any) -> bool:
    """An int or float, but not a bool: a bool sweep is two categories."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _label(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _distinct(labels: Sequence[str]) -> tuple[str, ...]:
    """The labels, with ``#2``, ``#3`` ... added to repeats so each is unique."""
    seen: set[str] = set()
    out = []
    for label in labels:
        candidate, k = label, 1
        while candidate in seen:
            k += 1
            candidate = f"{label} #{k}"
        seen.add(candidate)
        out.append(candidate)
    return tuple(out)


def _groups(n: int, cap: int) -> list[slice]:
    size = math.ceil(n / cap)
    return [slice(i, i + size) for i in range(0, n, size)]


def _bin(x: tuple, *series: np.ndarray) -> tuple[Any, ...]:
    """Average consecutive points down to at most MAX_CHART_POINTS.

    Returns the bin centers, then each series binned the same way.
    """
    groups = _groups(len(x), MAX_CHART_POINTS)
    centers = tuple(float(np.mean(np.asarray(x[g], dtype=float))) for g in groups)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return (centers, *(np.array([np.nanmean(s[g]) for g in groups]) for s in series))


def _noisy(base: _Profile, cand: _Profile) -> bool:
    """The spread between repeats is as large as the largest change between the sides."""
    noise = float(max(base.std.max(), cand.std.max()))
    change = float(np.max(np.abs(cand.mean - base.mean)))
    return noise > 0 and noise >= change


def _floats(values: Sequence[float] | np.ndarray) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def _sweep_labels(x: Sequence[Any]) -> tuple[str, ...]:
    if any(isinstance(v, float) for v in x):
        return tuple(_chart_nums([float(v) for v in x]))
    return tuple(_label(v) for v in x)


def plan_chart(
    base: _Profile, cand: _Profile, *, direction: str = "none", margin_percent: float = 10.0
) -> ChartPlan:
    """Choose the text form that shows a metric honestly.

    *direction* and *margin_percent* judge each row of a :class:`CategoryTable` and
    color each cell of a :class:`Heatmap`.
    """
    if set(base.swept) != set(cand.swept):
        return _overlap_inputs(base, cand)
    if len(base.swept) > 1:
        return _heatmap(base, cand, direction, margin_percent)
    if not base.swept:
        before, after = float(base.mean[0]), float(cand.mean[0])
        if not (math.isfinite(before) and math.isfinite(after)):
            missing = [
                side for side, v in (("before", before), ("after", after)) if not math.isfinite(v)
            ]
            return OverlapTable(
                None, (), f"Left out: every sample (no sample {' or '.join(missing)})."
            )
        if _noisy(base, cand):
            row = DiffRow("", before, after, float(base.std[0]), float(cand.std[0]))
            return DiffBars(None, (row,))
        if min(before, after) < 0:
            return DiffBars(None, (DiffRow("", before, after),))
        return BeforeAfterBars(before, after)
    name = base.swept[0]
    if base.x != cand.x or not (np.isfinite(base.mean).all() and np.isfinite(cand.mean).all()):
        return _overlap(name, base.x, base.mean, cand.x, cand.mean, [])
    x, before, after = base.x, base.mean, cand.mean
    if not all(_is_number(v) for v in x):
        labels = _distinct([_label(v) for v in x])
        return CategoryTable(
            name,
            tuple(
                CategoryRow(
                    label, float(b), float(c), unpaired_change(bp, cp, direction, margin_percent)
                )
                for label, b, c, bp, cp in zip(
                    labels, before, after, base.points, cand.points, strict=True
                )
            ),
        )
    noisy = _noisy(base, cand)
    before_std, after_std = base.std, cand.std
    if len(x) > MAX_CHART_POINTS:
        x, before, after, before_std, after_std = _bin(x, before, after, before_std, after_std)
    labels = _sweep_labels(x)
    if len(set(labels)) < len(labels):
        stds = zip(before_std, after_std, strict=True) if noisy else [(None, None)] * len(x)
        return DiffBars(
            name,
            tuple(
                DiffRow(label, float(b), float(c), *(None if s is None else float(s) for s in sd))
                for label, b, c, sd in zip(_distinct(labels), before, after, stds, strict=True)
            ),
        )
    if noisy:
        return BandChart(
            name, labels, _floats(before), _floats(after), _floats(before_std), _floats(after_std)
        )
    return SweepChart(name, labels, _floats(before), _floats(after))


def _named(name: str, values: Sequence[Any]) -> str:
    shown = ", ".join(_label(v) for v in values[:_MAX_NAMED])
    if len(values) > _MAX_NAMED:
        shown += f" and {len(values) - _MAX_NAMED} more"
    return f"{name}={shown}"


def _ordered(values: Sequence[Any]) -> list[Any]:
    unique = list(dict.fromkeys(values))
    return sorted(unique) if all(_is_number(v) for v in unique) else unique


def _overlap(
    name: str,
    base_x: Sequence[Any],
    base_mean: np.ndarray,
    cand_x: Sequence[Any],
    cand_mean: np.ndarray,
    notes: list[str],
) -> OverlapTable:
    """A table over the points both sides measured, and a note naming the rest."""
    before = dict(zip(base_x, (float(v) for v in base_mean), strict=True))
    after = dict(zip(cand_x, (float(v) for v in cand_mean), strict=True))
    shared: list[tuple[Any, float, float]] = []
    reasons: dict[str, list[Any]] = {}
    for v in _ordered([*base_x, *cand_x]):
        b, c = before.get(v), after.get(v)
        if b is None:
            reason = "after only"
        elif c is None:
            reason = "before only"
        elif not math.isfinite(b) and not math.isfinite(c):
            reason = "no sample on either side"
        elif not math.isfinite(b):
            reason = "no sample before"
        elif not math.isfinite(c):
            reason = "no sample after"
        else:
            shared.append((v, b, c))
            continue
        reasons.setdefault(reason, []).append(v)
    parts = [f"{_named(name, values)} ({reason})" for reason, values in reasons.items()]
    left_out = f"Left out: {'; '.join([*parts, *notes])}."
    x = tuple(v for v, _, _ in shared)
    before_v = np.array([b for _, b, _ in shared])
    after_v = np.array([c for _, _, c in shared])
    if len(x) > MAX_CHART_POINTS and all(_is_number(v) for v in x):
        x, before_v, after_v = _bin(x, before_v, after_v)
        left_out += f" {name} is binned to {len(x)} groups of consecutive values."
    labels = _distinct([_label(v) for v in x])
    rows = tuple(
        OverlapRow(label, float(b), float(c))
        for label, b, c in zip(labels, before_v, after_v, strict=True)
    )
    return OverlapTable(name, rows, left_out)


def _line(profile: _Profile, dim: str) -> tuple[tuple, np.ndarray]:
    """The mean at each value of *dim*, averaged over every other swept input."""
    if profile.cube is None:
        if profile.swept != (dim,):
            raise ValueError(f"a profile without a cube cannot be reduced to {dim!r}")
        return profile.x, profile.mean
    others = [d for d in profile.cube.dims if d != dim]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        line = profile.cube.mean(dim=others, skipna=True)
    return tuple(_plain(v) for v in line[dim].values), np.asarray(line.values, dtype=float)


def _overall(profile: _Profile) -> float:
    values = profile.mean if profile.cube is None else np.asarray(profile.cube.values, dtype=float)
    finite = values[np.isfinite(values)]
    return float(finite.mean()) if finite.size else math.nan


def _overlap_inputs(base: _Profile, cand: _Profile) -> OverlapTable:
    """The sides swept different inputs: compare over the first input both swept."""
    common = [d for d in base.swept if d in cand.swept]
    notes = []
    for side, mine, theirs in (
        ("before", base.swept, cand.swept),
        ("after", cand.swept, base.swept),
    ):
        only = [d for d in mine if d not in theirs]
        if only:
            notes.append(f"{', '.join(only)} (swept {side} only, averaged over)")
    if len(common) > 1:
        notes.append(f"{', '.join(common[1:])} (averaged over)")
    if not common:
        before, after = _overall(base), _overall(cand)
        missing = [
            side for side, v in (("before", before), ("after", after)) if not math.isfinite(v)
        ]
        if missing:
            notes.insert(0, f"every sample (no sample {' or '.join(missing)})")
            return OverlapTable(None, (), f"Left out: {'; '.join(notes)}.")
        rows = (OverlapRow("all points", before, after),)
        return OverlapTable(None, rows, f"Left out: {'; '.join(notes)}.")
    (bx, bm), (cx, cm) = _line(base, common[0]), _line(cand, common[0])
    return _overlap(common[0], bx, bm, cx, cm, notes)


def _bin_axis(
    labels: tuple, before: np.ndarray, after: np.ndarray, axis: int, cap: int
) -> tuple[tuple, np.ndarray, np.ndarray]:
    """Average consecutive numeric values along *axis* down to at most *cap*."""
    groups = _groups(len(labels), cap)
    centers = tuple(float(np.mean(np.asarray(labels[g], dtype=float))) for g in groups)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        binned = [
            np.stack(
                [
                    np.nanmean(np.take(a, range(len(labels))[g], axis=axis), axis=axis)
                    for g in groups
                ],
                axis=axis,
            )
            for a in (before, after)
        ]
    return centers, binned[0], binned[1]


def _heatmap(base: _Profile, cand: _Profile, direction: str, margin_percent: float) -> ChartPlan:
    import xarray as xr

    if base.cube is None or cand.cube is None:
        raise ValueError("a heatmap needs each profile's cube")
    row, col, *rest = base.swept
    order = [row, col, *rest]
    bc, cc = xr.align(base.cube.transpose(*order), cand.cube.transpose(*order), join="inner")
    left_out = []
    for dim in order:
        b_only = [v for v in base.cube[dim].values if v not in set(bc[dim].values)]
        c_only = [v for v in cand.cube[dim].values if v not in set(cc[dim].values)]
        for values, side in ((b_only, "before only"), (c_only, "after only")):
            if values:
                left_out.append(f"{_named(dim, [_plain(v) for v in values])} ({side})")
    if any(bc.sizes[d] == 0 for d in order):
        return OverlapTable(None, (), f"Left out: {'; '.join(left_out)}.")
    notes = [f"Left out: {part}." for part in left_out]
    layer = None
    if len(rest) == 1 and bc.sizes[rest[0]] <= MAX_HEATMAP_TABLES:
        layer = rest[0]
        names = _distinct(_sweep_labels([_plain(v) for v in bc[layer].values]))
        layers = [(name, bc.isel({layer: i}), cc.isel({layer: i})) for i, name in enumerate(names)]
    else:
        if rest:
            sizes = ", ".join(f"{d} ({bc.sizes[d]} values)" for d in rest)
            notes.append(f"Each cell is the mean over {sizes}.")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            layers = [(None, bc.mean(dim=rest, skipna=True), cc.mean(dim=rest, skipna=True))]
    row_values = tuple(_plain(v) for v in bc[row].values)
    col_values = tuple(_plain(v) for v in bc[col].values)
    grids = []
    for name, b, c in layers:
        before, after = np.asarray(b.values, dtype=float), np.asarray(c.values, dtype=float)
        rv, cv = row_values, col_values
        for axis, cap in ((0, MAX_HEATMAP_ROWS), (1, MAX_HEATMAP_COLS)):
            values = rv if axis == 0 else cv
            if len(values) > cap and all(_is_number(v) for v in values):
                values, before, after = _bin_axis(values, before, after, axis, cap)
                if axis == 0:
                    rv = values
                else:
                    cv = values
        grids.append(
            HeatmapGrid(
                name,
                tuple(tuple(float(v) for v in r) for r in before),
                tuple(tuple(float(v) for v in r) for r in after),
            )
        )
    for dim, before_n, after_n in (
        (row, len(row_values), len(rv)),
        (col, len(col_values), len(cv)),
    ):
        if after_n < before_n:
            notes.append(f"{dim} is binned to {after_n} groups of consecutive values.")
    return Heatmap(
        row,
        col,
        _distinct([_label(v) for v in rv]),
        _distinct([_label(v) for v in cv]),
        tuple(grids),
        layer,
        direction,
        margin_percent,
        tuple(notes),
    )


# --- Mermaid -----------------------------------------------------------------------


def _mermaid_text(text: str) -> str:
    """Strip what ends or breaks a quoted Mermaid string."""
    return re.sub(r"[\"`]", "", re.sub(r"[\n\r]+", " ", text))


def _claim_bounds(claim: Claim | None) -> list[float]:
    match claim:
        case None:
            return []
        case Threshold(bound=bound):
            return [bound]
        case Within(low=low, high=high):
            return [low, high]
        case _ as unreachable:
            assert_never(unreachable)


def _y_range(
    before: Sequence[float] | np.ndarray,
    after: Sequence[float] | np.ndarray,
    claim: Claim | None,
) -> tuple[float, float, float]:
    """A y range holding both series and the claim, from 0 unless 0 hides the change.

    Returns ``(lo, hi, step)``: both ends are whole multiples of ``step``.
    """
    before, after = np.asarray(before, dtype=float), np.asarray(after, dtype=float)
    values = np.concatenate([before, after, _claim_bounds(claim)])
    lo, hi = float(values.min()), float(values.max())
    change = float(np.max(np.abs(after - before)))
    with_zero = (min(lo, 0.0), max(hi, 0.0))
    if (
        with_zero[1] - with_zero[0] > 0
        and change / (with_zero[1] - with_zero[0]) >= _MIN_CHANGE_SHARE_FROM_ZERO
    ):
        lo, hi = with_zero
    span = hi - lo or abs(hi) or 1.0
    pad = 0.08 * span
    lo, hi = (lo if lo == 0 else lo - pad), (hi if hi == 0 else hi + pad)
    if hi == lo:  # every value and bound is 0
        hi = span
    # Round outward to two significant figures of the span, so the axis reads 0 --> 0.81.
    step = 10.0 ** (math.floor(math.log10(hi - lo)) - 1)
    return math.floor(lo / step) * step, math.ceil(hi / step) * step, step


def _num(value: float) -> str:
    return f"{value:.4g}"


def _chart_nums(values: Sequence[float]) -> list[str]:
    """Numbers xychart parses, with as few digits as keep distinct values distinct.

    Positional, since xychart's grammar has no exponent (1e+05). Values equal to
    12 significant digits count as one, so float noise (0.6 vs 0.6000000000000001)
    does not lengthen every number.
    """
    distinct = len({f"{v:.12g}" for v in values})
    for digits in range(4, 13):
        text = [
            np.format_float_positional(
                v, precision=digits, unique=False, fractional=False, trim="-"
            )
            for v in values
        ]
        if len(set(text)) == distinct:
            break
    return text


def _axis_end(value: float, step: float) -> str:
    """An axis end, exact to the ``step`` it is a multiple of, without an exponent."""
    decimals = max(0, -math.floor(math.log10(step)))
    return np.format_float_positional(
        value, precision=decimals, unique=False, fractional=True, trim="-"
    )


def _xy_front_matter(*colors: str) -> list[str]:
    return [
        "---",
        "config:",
        "  themeVariables:",
        "    xyChart:",
        f'      plotColorPalette: "{", ".join(colors)}"',
        "---",
    ]


def _band_series(
    plan: BandChart, claim: Claim | None
) -> tuple[list[str], tuple[float, float, float]]:
    """The six named lines of a BandChart and the y range that holds them."""
    b, a = np.asarray(plan.before), np.asarray(plan.after)
    bs, as_ = np.asarray(plan.before_std), np.asarray(plan.after_std)
    lines = {
        "before": b,
        "after": a,
        "before -1 std": b - bs,
        "before +1 std": b + bs,
        "after -1 std": a - as_,
        "after +1 std": a + as_,
    }
    y_range = _y_range(
        np.concatenate([b, b - bs, b + bs]), np.concatenate([a, a - as_, a + as_]), claim
    )
    text = _chart_nums([float(v) for values in lines.values() for v in values])
    n = len(plan.labels)
    series = [
        f'line "{line}" [{", ".join(text[i * n : (i + 1) * n])}]' for i, line in enumerate(lines)
    ]
    return series, y_range


def mermaid_chart(
    name: str,
    units: str | None,
    plan: BeforeAfterBars | SweepChart | BandChart,
    claim: Claim | None,
) -> str:
    """The fenced ``xychart-beta`` block for a plan that has one."""
    metric = _mermaid_text(f"{name} ({units})" if units else name)
    match plan:
        case BeforeAfterBars(before=before, after=after):
            title = f"{metric}: before vs after"
            x_axis = 'x-axis ["before", "after"]'
            lo, hi, step = _y_range([before], [after], claim)
            series = [f"bar [{', '.join(_chart_nums([before, after]))}]"]
            front_matter = _xy_front_matter(MERMAID_AFTER_COLOR)
        case SweepChart(input_name=input_name, labels=labels, before=before, after=after):
            title = f"{metric}: before vs after"
            quoted = ", ".join(f'"{_mermaid_text(label)}"' for label in labels)
            x_axis = f'x-axis "{_mermaid_text(input_name)}" [{quoted}]'
            lo, hi, step = _y_range(before, after, claim)
            text = _chart_nums([*before, *after])
            series = [
                f'line "before" [{", ".join(text[: len(before)])}]',
                f'line "after" [{", ".join(text[len(before) :])}]',
            ]
            front_matter = _xy_front_matter(MERMAID_BEFORE_COLOR, MERMAID_AFTER_COLOR)
        case BandChart(input_name=input_name, labels=labels):
            title = f"{metric}: before vs after, pale lines = ±1 std"
            quoted = ", ".join(f'"{_mermaid_text(label)}"' for label in labels)
            x_axis = f'x-axis "{_mermaid_text(input_name)}" [{quoted}]'
            series, (lo, hi, step) = _band_series(plan, claim)
            front_matter = _xy_front_matter(
                MERMAID_BEFORE_COLOR,
                MERMAID_AFTER_COLOR,
                MERMAID_BEFORE_BAND_COLOR,
                MERMAID_BEFORE_BAND_COLOR,
                MERMAID_AFTER_BAND_COLOR,
                MERMAID_AFTER_BAND_COLOR,
            )
        case _ as unreachable:
            assert_never(unreachable)
    lines = [
        "```mermaid",
        *front_matter,
        "xychart-beta",
        f'    title "{title}"',
        f"    {x_axis}",
        f'    y-axis "{metric}" {_axis_end(lo, step)} --> {_axis_end(hi, step)}',
        *(f"    {s}" for s in series),
        "```",
    ]
    return "\n".join(lines)


def _cell(text: str) -> str:
    """Text that stays inside one Markdown table cell."""
    return re.sub(r"[\n\r]+", " ", text).replace("|", "\\|")


def _ci_cell(change: dict) -> str:
    if change["ci_low"] is None:
        return change["stat_verdict"]
    return f"[{_num(change['ci_low'])}, {_num(change['ci_high'])}] → {change['stat_verdict']}"


def category_table(name: str, units: str | None, plan: CategoryTable) -> str:
    """A Markdown table: one row per category, with the change and its 95% CI."""
    metric = f"{name} ({units})" if units else name
    lines = [
        f"**{_cell(metric)}** by {_cell(plan.input_name)}: before vs after",
        "",
        f"| {_cell(plan.input_name)} | before | after | change | 95% CI |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| {_cell(row.label)} | {_num(row.before)} | {_num(row.after)} "
        f"| {row.after - row.before:+.4g} | {_ci_cell(row.change)} |"
        for row in plan.rows
    )
    return "\n".join(lines)


# Bar width in characters, and the eighth blocks that end a positive bar.
DIFF_BAR_WIDTH = 30
_EIGHTHS = " ▏▎▍▌▋▊▉"
# Text that would close a Markdown fence early.
_FENCE = "```"


def _text_bar(value: float, lo: float, hi: float) -> str:
    """A bar of DIFF_BAR_WIDTH cells over [lo, hi], grown from a zero column."""
    span = (hi - lo) or 1.0
    neg_width = round(-lo / span * DIFF_BAR_WIDTH)
    pos_width = DIFF_BAR_WIDTH - neg_width
    cells = abs(value) / span * DIFF_BAR_WIDTH
    if value < 0:
        # Eighth blocks fill from the left, so a bar that grows leftward uses whole cells.
        n = min(neg_width, round(cells))
        left, right = " " * (neg_width - n) + "█" * n, " " * pos_width
    else:
        full, eighth = divmod(min(round(cells * 8), pos_width * 8), 8)
        left = " " * neg_width
        right = ("█" * full + (_EIGHTHS[eighth] if eighth else "")).ljust(pos_width)
    return left + ("│" if lo < 0 else "") + right


def diff_bars(name: str, units: str | None, plan: DiffBars) -> str:
    """A ``diff`` fence of text bars: a red ``-`` line before and a green ``+`` line after."""
    metric = f"{name} ({units})" if units else name
    unit = f" {units}" if units else ""
    values = [v for row in plan.rows for v in (row.before, row.after)]
    lo, hi = min(0.0, *values), max(0.0, *values)
    width = max((len(row.label) for row in plan.rows), default=0)
    by = f" by {_cell(plan.input_name)}" if plan.input_name else ""
    lines = [
        f"**{_cell(metric)}**{by}: before vs after",
        "",
        _FENCE + "diff",
        f"  bars from 0, axis {_num(lo)} to {_num(hi)}{unit}",
    ]

    def number(value: float, std: float | None) -> str:
        return _num(value) + ("" if std is None else f" ± {_num(std)}")

    # Numbers go before the bars: block glyphs are not exactly monospace in every font,
    # so a column after the bars would drift.
    numbers = [
        number(v, s)
        for r in plan.rows
        for v, s in ((r.before, r.before_std), (r.after, r.after_std))
    ]
    num_width = max(len(text) for text in numbers)
    for row in plan.rows:
        label = f"{row.label.ljust(width)}  " if plan.input_name else ""
        for sign, side, value, std in (
            ("-", "before", row.before, row.before_std),
            ("+", "after ", row.after, row.after_std),
        ):
            text = number(value, std).rjust(num_width)
            line = f"{sign} {label}{side}  {text}  {_text_bar(value, lo, hi)}".rstrip()
            lines.append(line.replace(_FENCE, "'''"))
    lines.append(_FENCE)
    return "\n".join(lines)


def _percent_change(before: float, after: float) -> float | None:
    if not (math.isfinite(before) and math.isfinite(after)) or before == 0:
        return None
    return (after - before) / abs(before) * 100.0


# From here up a percent change prints with no decimals: +250%, not +2.5e+02%.
_WHOLE_PERCENT = 100


def _pct(value: float) -> str:
    return f"{value:+.0f}%" if abs(value) >= _WHOLE_PERCENT else f"{value:+.1f}%"


def _heat_mark(change: float, direction: str, margin: float) -> str:
    """The color square for a percent change: better/worse by the metric's direction."""
    if change == 0 or abs(change) < margin:
        return "⬜"
    sign = {"minimize": -1.0, "maximize": 1.0}.get(direction)
    if sign is None:
        return "🟪" if change < 0 else "🟨"
    gain = change * sign
    if gain > 0:
        return "🟦" if gain >= 2 * margin else "🟩"
    return "🟥" if -gain >= 2 * margin else "🟧"


def _heat_legend(direction: str, margin: float) -> str:
    m, m2 = _num(margin), _num(2 * margin)
    within = f"⬜ within ±{m}%" if margin > 0 else "⬜ no change"
    if direction in ("minimize", "maximize"):
        better = "lower" if direction == "minimize" else "higher"
        return (
            f"🟦 better by ≥ {m2}% · 🟩 better by ≥ {m}% · {within} · 🟧 worse by ≥ {m}%"
            f" · 🟥 worse by ≥ {m2}% · n/a: no sample, or before is 0 ({better} is better)"
        )
    return (
        f"🟪 down by ≥ {m}% · {within} · 🟨 up by ≥ {m}% · n/a: no sample, or before is 0"
        " (no direction is set, so the color shows only which way it moved)"
    )


def heatmap_table(name: str, units: str | None, plan: Heatmap) -> str:
    """One Markdown table per grid: each cell is the percent change with its color."""
    metric = f"{name} ({units})" if units else name
    row, col = _cell(plan.row_input), _cell(plan.col_input)
    lines = [
        f"**{_cell(metric)}**: % change after vs before, by {row} (rows) and {col} (columns)",
    ]
    for grid in plan.grids:
        lines.append("")
        if grid.layer is not None and plan.layer_input is not None:
            lines += [f"{_cell(plan.layer_input)} = {_cell(grid.layer)}:", ""]
        header = " | ".join(_cell(c) for c in plan.col_labels)
        lines.append(f"| {row} ↓ {col} → | {header} |")
        lines.append("| --- |" + " ---: |" * len(plan.col_labels))
        for label, before_row, after_row in zip(
            plan.row_labels, grid.before, grid.after, strict=True
        ):
            cells = []
            for b, a in zip(before_row, after_row, strict=True):
                change = _percent_change(b, a)
                if change is None:
                    cells.append("n/a")
                else:
                    mark = _heat_mark(change, plan.direction, plan.margin_percent)
                    cells.append(f"{mark} {_pct(change)}")
            lines.append(f"| {_cell(label)} | " + " | ".join(cells) + " |")
    lines += ["", _heat_legend(plan.direction, plan.margin_percent)]
    if plan.notes:
        lines += ["", " ".join(plan.notes)]
    return "\n".join(lines)


def overlap_table(name: str, units: str | None, plan: OverlapTable) -> str:
    """A table over the points both sides measured, then what was left out."""
    metric = f"{name} ({units})" if units else name
    if not plan.rows:
        return f"**{_cell(metric)}**: no point has a sample on both sides.\n\n{plan.left_out}"
    head = _cell(plan.input_name) if plan.input_name else "points"
    by = f" by {head}" if plan.input_name else ""
    lines = [
        f"**{_cell(metric)}**{by}: before vs after, over the points both sides measured",
        "",
        f"| {head} | before | after | change |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {_cell(r.label)} | {_num(r.before)} | {_num(r.after)} | {r.after - r.before:+.4g} |"
        for r in plan.rows
    )
    lines += ["", plan.left_out]
    return "\n".join(lines)


def _csv_num(value: float | None) -> str:
    return "" if value is None or not math.isfinite(value) else f"{value:.10g}"


def _diff_data(plan: DiffBars) -> list[list[str]]:
    n = _csv_num
    spread = any(r.before_std is not None for r in plan.rows)
    head = ["before", "before_std", "after", "after_std"] if spread else ["before", "after"]
    label = [plan.input_name] if plan.input_name else []
    out = [label + head]
    for r in plan.rows:
        if spread:
            values = [n(r.before), n(r.before_std), n(r.after), n(r.after_std)]
        else:
            values = [n(r.before), n(r.after)]
        out.append(([r.label] if plan.input_name else []) + values)
    return out


def _heatmap_data(plan: Heatmap) -> list[list[str]]:
    n = _csv_num
    layer = [plan.layer_input] if plan.layer_input else []
    out = [[plan.row_input, plan.col_input, *layer, "before", "after", "change_percent"]]
    for grid in plan.grids:
        extra = [grid.layer or ""] if plan.layer_input else []
        for label, before_row, after_row in zip(
            plan.row_labels, grid.before, grid.after, strict=True
        ):
            for col, b, a in zip(plan.col_labels, before_row, after_row, strict=True):
                out.append([label, col, *extra, n(b), n(a), n(_percent_change(b, a))])
    return out


def _data_rows(plan: ChartPlan) -> list[list[str]]:
    """The points a plan draws, as CSV rows under a header."""
    n = _csv_num
    match plan:
        case BeforeAfterBars(before=before, after=after):
            return [["before", "after"], [n(before), n(after)]]
        case SweepChart(input_name=name, labels=labels, before=before, after=after):
            rows = zip(labels, before, after, strict=True)
            return [[name, "before", "after"]] + [[label, n(b), n(a)] for label, b, a in rows]
        case BandChart(input_name=name, labels=labels):
            rows = zip(
                labels, plan.before, plan.before_std, plan.after, plan.after_std, strict=True
            )
            return [[name, "before", "before_std", "after", "after_std"]] + [
                [label, n(b), n(bs), n(a), n(as_)] for label, b, bs, a, as_ in rows
            ]
        case DiffBars():
            return _diff_data(plan)
        case CategoryTable(input_name=name, rows=rows):
            return [[name, "before", "after", "change", "ci_low", "ci_high"]] + [
                [
                    r.label,
                    n(r.before),
                    n(r.after),
                    n(r.after - r.before),
                    n(r.change["ci_low"]),
                    n(r.change["ci_high"]),
                ]
                for r in rows
            ]
        case Heatmap():
            return _heatmap_data(plan)
        case OverlapTable(input_name=name, rows=rows):
            return [[name or "points", "before", "after"]] + [
                [r.label, n(r.before), n(r.after)] for r in rows
            ]
        case _ as unreachable:
            assert_never(unreachable)


def data_block(name: str, plan: ChartPlan) -> str:
    """A collapsed ``<details>`` block with a CSV fence of the points the chart shows."""
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(_data_rows(plan))
    body = buffer.getvalue().replace(_FENCE, "'''")
    return (
        f"<details><summary>data: {html.escape(name)}</summary>\n\n"
        f"{_FENCE}csv\n{body}{_FENCE}\n\n</details>"
    )


def radar_chart(metrics: Sequence[dict]) -> str | None:
    """A ``radar-beta`` block of every metric scaled so its baseline mean is 1, with notes.

    Returns None below :data:`MIN_RADAR_METRICS` compared metrics. A metric whose
    baseline mean is 0, negative or non-finite, or whose mean changes sign, cannot be
    scaled that way: it is left off and named under the chart.
    """
    if len(metrics) < MIN_RADAR_METRICS:
        return None
    axes: list[tuple[dict, float]] = []
    skipped: list[str] = []
    for entry in metrics:
        base, cand = entry["baseline_value"], entry["current_value"]
        name = f"`{entry['variable']}`"
        if base is None or not math.isfinite(base):
            skipped.append(f"{name} (baseline mean is not finite)")
        elif base == 0:
            skipped.append(f"{name} (baseline mean is 0)")
        elif base < 0:
            skipped.append(f"{name} (baseline mean is negative)")
        elif cand is None or not math.isfinite(cand):
            skipped.append(f"{name} (candidate mean is not finite)")
        elif (cand < 0) != (base < 0) and cand != 0:
            skipped.append(f"{name} (the mean changed sign)")
        else:
            axes.append((entry, cand / base))
    notes = [f"Not on the radar: {', '.join(skipped)}."] if skipped else []
    if len(axes) < MIN_RADAR_METRICS:
        count = "1 metric" if len(axes) == 1 else f"{len(axes)} metrics"
        pronoun = "its" if len(axes) == 1 else "their"
        return "\n".join([f"No radar: only {count} can be scaled to {pronoun} baseline.", *notes])
    ratios = [ratio for _, ratio in axes]
    top = math.ceil(max(1.0, *ratios) * 1.1 * 10) / 10
    text = _chart_nums([1.0, *ratios])
    one, after = text[0], text[1:]
    labels = ", ".join(
        f'm{i}["{_mermaid_text(entry["variable"])}"]' for i, (entry, _) in enumerate(axes)
    )
    better = {"minimize": [], "maximize": []}
    for entry, _ in axes:
        better.get(entry["direction"], []).append(f"`{entry['variable']}`")
    direction_notes = [
        f"{word} is better for {', '.join(names)}."
        for word, names in (("Lower", better["minimize"]), ("Higher", better["maximize"]))
        if names
    ]
    lines = [
        "```mermaid",
        "---",
        "config:",
        # Straight edges: a smoothed curve between axes would draw values no metric has.
        "  radar:",
        "    curveTension: 0",
        "  themeVariables:",
        f'    cScale0: "{MERMAID_BEFORE_COLOR}"',
        f'    cScale1: "{MERMAID_AFTER_COLOR}"',
        # Rings get in the way of the curves, and the "before" curve already marks 1:
        # no rings, pale curve fills and thick strokes keep both curves readable.
        "    radar:",
        "      curveOpacity: 0.12",
        "      curveStrokeWidth: 3",
        "      graticuleOpacity: 0",
        "      graticuleStrokeWidth: 0",
        f'      graticuleColor: "{MERMAID_BEFORE_COLOR}"',
        f'      axisColor: "{MERMAID_BEFORE_COLOR}"',
        "---",
        "radar-beta",
        "  title Metrics relative to before (before = 1)",
        f"  axis {labels}",
        f'  curve before["before"]{{{", ".join([one] * len(axes))}}}',
        f'  curve after["after"]{{{", ".join(after)}}}',
        f"  max {_chart_nums([top])[0]}",
        "  min 0",
        "  ticks 1",
        "  graticule polygon",
        "```",
        "",
        " ".join(
            [
                (
                    "Each axis is one metric's mean divided by its baseline mean,"
                    " so before is 1 on every axis."
                ),
                *direction_notes,
            ]
        ),
        *notes,
    ]
    return "\n".join(lines)


# --- captions --------------------------------------------------------------------


_CI_METHODS = {"paired_bootstrap": "paired bootstrap", "bootstrap": "bootstrap"}
_MOVED = (IMPROVED, REGRESSED, INCREASED, DECREASED)


def _verdicts_agree(threshold: str, verdict: str) -> bool:
    """An undirected metric's threshold verdict calls any move ``regressed``."""
    return threshold == verdict or (threshold == REGRESSED and verdict in (INCREASED, DECREASED))


def change_line(metric: dict, units: str | None) -> str | None:
    """The mean change, its 95% CI and the stat verdict, from the metric's ``change``."""
    change = metric.get("change")
    if change is None:
        return None
    unit = f" {units}" if units else ""
    verdict = change["stat_verdict"]
    if change["ci_low"] is None:
        if verdict == TOO_FEW_SAMPLES:
            counts = f"n={change['n_baseline']} vs {change['n_candidate']}"
            if change["method"] == "paired_bootstrap":
                counts = f"n={change['n']}"
            return f"change: {verdict} for a CI ({counts})"
        return f"change: {verdict} ({change.get('reason', 'no estimate')})"
    if change["method"] == "paired_bootstrap":
        counts = f"n={change['n']}"
    else:
        counts = f"n={change['n_baseline']} vs {change['n_candidate']}"
    level = f"{change['ci_level'] * 100:g}%"
    line = (
        f"change {change['mean_diff']:+.4g}{unit}, {level} CI "
        f"[{_num(change['ci_low'])}, {_num(change['ci_high'])}]"
        f" ({_CI_METHODS.get(change['method'], change['method'])}, {counts}) → {verdict}"
    )
    threshold = metric["verdict"]
    if not _verdicts_agree(threshold, verdict) and (threshold in _MOVED or verdict in _MOVED):
        line += f"; the threshold verdict says {threshold}"
    return line


def _where(inputs: dict) -> str:
    return ", ".join(f"{k}={_label(v)}" for k, v in inputs.items())


def _claim_side(side: dict) -> str:
    if side["holds"] is None:
        return "not measured"
    verdict = "holds" if side["holds"] else "fails"
    worst = side["worst_value"]
    worst_text = "non-finite" if worst is None else _num(worst)
    return f"{verdict} (worst {worst_text} at {_where(side['worst_inputs'])})"


def _revision(side: dict) -> str:
    revision = side["provenance"].get("source_revision")
    return f"`{revision}`" if revision else "revision unknown"


def caption(metric: dict, units: str | None, comparison: dict, samples: tuple[int, int]) -> str:
    """The verdict, values, claim and provenance lines under a metric's chart."""
    unit = f" {units}" if units else ""
    base, cand = metric["baseline_value"], metric["current_value"]
    values = (
        f"{'n/a' if base is None else _num(base)} → {'n/a' if cand is None else _num(cand)}{unit}"
    )
    if metric["change_percent"] is not None:
        values += f" ({metric['change_percent']:+.1f}%)"
    parts = [f"**{metric['variable']}** {metric['verdict']}: mean {values}"]
    if claim := metric.get("claim"):
        parts.append(
            f"claim `{claim['claim']}`: baseline {_claim_side(claim['baseline'])}"
            f" → candidate {_claim_side(claim['candidate'])}"
        )
    lines = [" · ".join(parts)]
    if (change := change_line(metric, units)) is not None:
        lines.append(change)
    provenance = (
        f"<sub>baseline {_revision(comparison['baseline'])}, {samples[0]} samples · "
        f"candidate {_revision(comparison['candidate'])}, {samples[1]} samples</sub>"
    )
    return "  \n".join([*lines, provenance])


def png_name(variable: str) -> str:
    """The file name a metric's PNG is written under."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", variable) + ".png"


# --- assembly --------------------------------------------------------------------


@dataclass(frozen=True)
class _Metric:
    entry: dict  # the comparison record
    units: str | None
    claim: Claim | None
    base: _Profile
    cand: _Profile
    plan: ChartPlan
    # Every sample of each side, for an image and its CSV.
    base_da: xr.DataArray
    cand_da: xr.DataArray


def _metrics(baseline: BenchResult, candidate: BenchResult, comparison: dict) -> list[_Metric]:
    base_ds, cand_ds = _snapshot_ds(baseline), _snapshot_ds(candidate)
    result_vars = {rv.name: rv for rv in candidate.bench_cfg.result_vars}
    out = []
    for entry in comparison["metrics"]:
        name = entry["variable"]
        rv = result_vars.get(name)
        base, cand = _profile(base_ds[name]), _profile(cand_ds[name])
        margin = (entry.get("change") or {}).get("equivalence_percent", 10.0)
        plan = plan_chart(base, cand, direction=entry["direction"], margin_percent=margin)
        out.append(
            _Metric(
                entry=entry,
                units=getattr(rv, "units", None),
                claim=getattr(rv, "claim", None),
                base=base,
                cand=cand,
                plan=plan,
                base_da=base_ds[name],
                cand_da=cand_ds[name],
            )
        )
    return out


PNG_URL_BASE_FLAG_DEPRECATED = (
    "--png-url-base is deprecated and ignored: evidence is text only, so evidence.md "
    "links no image. Use --png-dir to write PNGs for local viewing."
)
PNG_URL_BASE_DEPRECATED = (
    "png_url_base is deprecated and ignored: evidence is text only, so the Markdown "
    "links no image. Write PNGs for local viewing with png_dir."
)


def _summary(comparison: dict) -> str:
    counts = comparison["summary"]
    return (
        f"**bencher A/B:** {counts['improved']} improved, {counts['regressed']} regressed, "
        f"{counts['unchanged']} unchanged — baseline {_revision(comparison['baseline'])} → "
        f"candidate {_revision(comparison['candidate'])}"
    )


def unpaired_warnings(comparison: dict) -> list[str]:
    """One message per metric that only one side declares."""
    unpaired = comparison.get("unpaired", {})
    return [
        *(
            f"`{name}` is only in the candidate, so it has no baseline to compare against"
            for name in unpaired.get("candidate_only", [])
        ),
        *(
            f"`{name}` is only in the baseline, so the candidate does not measure it"
            for name in unpaired.get("baseline_only", [])
        ),
    ]


def _claims_block(comparison: dict) -> str | None:
    """Every claim the candidate declares, judged whether or not the baseline has it."""
    claims = comparison.get("claims", [])
    if not claims:
        return None
    lines = ["**Claims**", ""]
    for c in claims:
        base = c["baseline"]
        base_text = "no baseline" if base is None else f"baseline {_claim_side(base)}"
        lines.append(
            f"- `{c['variable']}` `{c['claim']}`: candidate {_claim_side(c['candidate'])}"
            f" · {base_text}"
        )
    return "\n".join(lines)


def _unpaired_block(comparison: dict) -> str | None:
    warnings_ = unpaired_warnings(comparison)
    if not warnings_:
        return None
    return "\n".join(["**Not compared**", "", *(f"- {w}" for w in warnings_)])


def _chart(m: _Metric) -> str:
    name = m.entry["variable"]
    match m.plan:
        case BeforeAfterBars() | SweepChart() | BandChart():
            return mermaid_chart(name, m.units, m.plan, m.claim)
        case CategoryTable():
            return category_table(name, m.units, m.plan)
        case DiffBars():
            return diff_bars(name, m.units, m.plan)
        case Heatmap():
            return heatmap_table(name, m.units, m.plan)
        case OverlapTable():
            return overlap_table(name, m.units, m.plan)
        case _ as unreachable:
            assert_never(unreachable)


def _image_block(name: str, png_url: str, csv_url: str | None) -> str:
    """The linked image of one metric, and a link to the samples it draws."""
    alt = re.sub(r"[\[\]\n\r]", "", name)
    lines = [f"![{alt}: before vs after]({png_url})"]
    if csv_url:
        lines.append(f"<sub>[samples (CSV)]({csv_url})</sub>")
    return "  \n".join(lines)


def _markdown(
    metrics: list[_Metric],
    comparison: dict,
    images: Mapping[str, tuple[str, str | None]] | None = None,
) -> str:
    blocks = [_summary(comparison)]
    blocks += [b for b in (_claims_block(comparison), _unpaired_block(comparison)) if b]
    if (radar := radar_chart([m.entry for m in metrics])) is not None:
        blocks.append(radar)
    for m in metrics:
        name = m.entry["variable"]
        samples = (m.base.samples, m.cand.samples)
        image = (images or {}).get(name)
        blocks.append(
            "\n\n".join(
                [
                    *([_image_block(name, *image)] if image else []),
                    _chart(m),
                    caption(m.entry, m.units, comparison, samples),
                    data_block(name, m.plan),
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def evidence_markdown(
    baseline: BenchResult,
    candidate: BenchResult,
    *,
    comparison: dict | None = None,
    png_url_base: str | None = None,
    run_cfg: BenchRunCfg | None = None,
) -> str:
    """Markdown for a PR's ``## Evidence`` section: a chart, caption and data per metric.

    Every chart is text GitHub draws in the PR body: no image, no external resource.
    Above the charts, a **Claims** list judges every claim the candidate declares,
    with "no baseline" for a metric the baseline does not measure, and a **Not
    compared** list names each metric only one side declares.

    Args:
        baseline: The result before the change.
        candidate: The result after the change.
        comparison: A :func:`compare_results` dict for the pair, when already computed.
        png_url_base: Deprecated and ignored, with a :class:`DeprecationWarning`: the
            Markdown links no image.
        run_cfg: Forwarded to :func:`compare_results` when *comparison* is omitted.
    """
    if png_url_base is not None:
        warnings.warn(PNG_URL_BASE_DEPRECATED, DeprecationWarning, stacklevel=2)
    if comparison is None:
        comparison = compare_results(baseline, candidate, run_cfg=run_cfg)
    return _markdown(_metrics(baseline, candidate, comparison), comparison)


# --- PNG -------------------------------------------------------------------------


_Side = tuple[_Profile, str, str, str]  # profile, legend label, color, line style


def _draw(ax: Axes, sides: Sequence[_Side]) -> None:
    profiles = [profile for profile, *_ in sides]
    if not any(p.swept for p in profiles):
        ax.bar(
            range(len(sides)),
            [p.mean[0] for p in profiles],
            yerr=[p.std[0] for p in profiles],
            color=[color for _, _, color, _ in sides],
            capsize=6,
            width=0.5,
        )
        ax.set_xticks(range(len(sides)), [label for _, label, _, _ in sides])
        return
    xs = tuple(v for p in profiles for v in p.x)
    numeric = all(isinstance(v, (int, float)) for v in xs)
    for profile, label, color, style in sides:
        if not profile.swept:
            # One value across the other side's sweep: a level line with its band.
            mean, std = profile.mean[0], profile.std[0]
            ax.axhline(mean, linestyle=style, color=color, label=label, linewidth=2)
            ax.axhspan(mean - std, mean + std, color=color, alpha=0.18)
            continue
        if numeric:
            x = np.asarray(profile.x, dtype=float)
        else:
            categories = list(dict.fromkeys(xs))
            x = np.array([categories.index(v) for v in profile.x], dtype=float)
            ax.set_xticks(range(len(categories)), [_label(c) for c in categories])
        ax.plot(x, profile.mean, style, marker="o", color=color, label=label, linewidth=2)
        ax.fill_between(
            x, profile.mean - profile.std, profile.mean + profile.std, color=color, alpha=0.18
        )
    ax.set_xlabel(next(p.swept[0] for p in profiles if p.swept))


def _draw_claim(ax: Axes, claim: Claim | None) -> None:
    for bound in _claim_bounds(claim):
        ax.axhline(bound, color=_CLAIM_COLOR, linestyle=":", linewidth=1.5)
    if claim is not None:
        ax.plot([], [], color=_CLAIM_COLOR, linestyle=":", label=f"claim {claim}")


def _render_png(m: _Metric, path: Path, *, detail: bool = False) -> Path:
    """Draw one metric's PNG at *path*.

    By default the mean ± 1 std of each side; with *detail*, the PR-body image:
    a heatmap, or every repeat with its box.
    """
    # Figure without pyplot: no global backend state, safe in any process.
    from matplotlib.figure import Figure

    if detail:
        from matplotlib.lines import Line2D

        name = m.entry["variable"]
        metric = f"{name} ({m.units})" if m.units else name
        if isinstance(m.plan, Heatmap):
            fig = _render_heatmap_image(m.plan, metric)
            fig.savefig(path, facecolor=_IMAGE_SURFACE, bbox_inches="tight")
            return path
        fig = Figure(figsize=(8.8, 4.6), dpi=100, facecolor=_IMAGE_SURFACE)
        ax = fig.add_subplot()
        _style(ax)
        xlabel = _draw_repeats(ax, m)
        _draw_claim(ax, m.claim)
        handles = [
            Line2D(
                [],
                [],
                marker="D",
                linestyle="",
                color=_IMAGE_BEFORE_COLOR,
                markerfacecolor=_IMAGE_SURFACE,
                label="before",
            ),
            Line2D([], [], marker="D", linestyle="", color=_IMAGE_AFTER_COLOR, label="after"),
        ]
        if m.claim is not None:
            handles.append(
                Line2D([], [], color=_CLAIM_COLOR, linestyle=":", label=f"claim {m.claim}")
            )
        ax.legend(handles=handles, loc="best", frameon=False, fontsize=9)
        ax.set_xlabel(xlabel, color=_IMAGE_MUTED_INK)
        ax.set_ylabel(metric, color=_IMAGE_MUTED_INK)
        rest = m.base.swept[1:]
        pooled = f", pooled over {', '.join(rest)}" if rest else ""
        ax.set_title(
            f"{metric}: every repeat before vs after\n"
            f"dots = repeats, box = quartiles, ◆ = mean ± 1 std{pooled}",
            fontsize=11,
            color=_IMAGE_INK,
            loc="left",
        )
        fig.tight_layout()
        fig.savefig(path, facecolor=_IMAGE_SURFACE)
        return path
    name = m.entry["variable"]
    fig = Figure(figsize=(8.8, 4.4), dpi=100, facecolor="white")
    sides: list[_Side] = [
        (m.base, "before", _BEFORE_COLOR, "--"),
        (m.cand, "after", _AFTER_COLOR, "-"),
    ]
    split = bool(m.base.swept) and bool(m.cand.swept) and m.base.swept[0] != m.cand.swept[0]
    if split:
        # Each side swept its own input: one panel per input, sharing the metric axis.
        axes = list(fig.subplots(1, 2, sharey=True))
        groups = [sides[:1], sides[1:]]
    else:
        axes, groups = [fig.add_subplot()], [sides]
    for ax, group in zip(axes, groups, strict=True):
        _draw(ax, group)
        _draw_claim(ax, m.claim)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", frameon=False)
    swept = m.base.swept if len(m.base.swept) >= len(m.cand.swept) else m.cand.swept
    rest = f", mean over {', '.join(swept[1:])}" if len(swept) > 1 else ""
    metric = f"{name} ({m.units})" if m.units else name
    spread = "band" if swept else "error bar"
    title = f"{metric}: before (grey) vs after (blue), {spread} = ±1 std{rest}"
    if split:
        fig.suptitle(title, fontsize=12)
    else:
        axes[0].set_title(title, fontsize=12)
    axes[0].set_ylabel(metric)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    return path


def write_evidence_pngs(
    baseline: BenchResult,
    candidate: BenchResult,
    out_dir: str | Path,
    *,
    comparison: dict | None = None,
    run_cfg: BenchRunCfg | None = None,
) -> dict[str, Path]:
    """Write one before/after PNG per compared metric; return ``{variable: path}``."""
    if comparison is None:
        comparison = compare_results(baseline, candidate, run_cfg=run_cfg)
    out_dir = Path(out_dir)
    return {
        m.entry["variable"]: _render_png(m, out_dir / png_name(m.entry["variable"]))
        for m in _metrics(baseline, candidate, comparison)
    }


# --- images for the PR body ------------------------------------------------------

# Colors of the linked images (validated with the dataviz palette checks): "before" is
# the muted reference grey with hollow marks, "after" the first categorical blue, filled.
_IMAGE_BEFORE_COLOR = "#898781"
_IMAGE_AFTER_COLOR = "#2a78d6"
_IMAGE_SURFACE = "#fcfcfb"
_IMAGE_INK = "#0b0b0b"
_IMAGE_MUTED_INK = "#52514e"
_IMAGE_GRID = "#e1e0d9"
# Heatmap poles: better and worse by the metric's direction, with a grey midpoint.
_IMAGE_BETTER = "#2a78d6"
_IMAGE_WORSE = "#e34948"
_IMAGE_DOWN = "#6250d6"  # no direction: down and up
_IMAGE_UP = "#eda100"
_IMAGE_MID = "#f0efec"
# Past this many swept points, an image draws each repeat and the mean, not a box per point.
_MAX_IMAGE_BOXES = MAX_CHART_POINTS
# Past this many heatmap cells, a cell carries its color only, not its percent.
_MAX_ANNOTATED_CELLS = 120


def _image_adds_information(m: _Metric) -> bool:
    """True when an image shows more than the metric's text chart.

    A heatmap image draws the percent change as a continuous color; a box per point
    shows the spread of the repeats, so it needs more than one sample at a point.
    """
    match m.plan:
        case Heatmap():
            return True
        case OverlapTable():
            return False
        case _:
            return max(_most_per_point(m.base), _most_per_point(m.cand)) > 1


def _most_per_point(profile: _Profile) -> int:
    if profile.swept:
        return max((len(p) for p in profile.points), default=0)
    return profile.samples


def _samples_csv(m: _Metric) -> str:
    """Every finite sample of both sides as CSV: ``side``, each dimension, the value."""
    name = m.entry["variable"]
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    dims = list(m.cand_da.dims) + [d for d in m.base_da.dims if d not in m.cand_da.dims]
    writer.writerow(["side", *dims, name])
    for side, da in (("before", m.base_da), ("after", m.cand_da)):
        values = np.asarray(da.astype(float).values)
        coords = [np.asarray(da[d].values) for d in da.dims]
        for index in np.ndindex(values.shape):
            value = float(values[index])
            if not math.isfinite(value):
                continue
            at = {d: _plain(c[i]) for d, c, i in zip(da.dims, coords, index, strict=True)}
            writer.writerow([side, *(at.get(d, "") for d in dims), f"{value:.10g}"])
    return buffer.getvalue()


def _style(ax: Axes) -> None:
    ax.set_facecolor(_IMAGE_SURFACE)
    ax.grid(True, axis="y", color=_IMAGE_GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#c3c2b7")
    ax.tick_params(colors=_IMAGE_MUTED_INK, labelsize=9)


def _side_marks(
    ax: Axes,
    groups: Sequence[np.ndarray],
    positions: np.ndarray,
    color: str,
    filled: bool,
    *,
    boxes: bool,
    width: float,
) -> None:
    """One side: a box per point, every repeat as a dot, and the mean with ±1 std."""
    rng = np.random.default_rng(0)  # fixed jitter: the same results draw the same image
    face = color if filled else _IMAGE_SURFACE
    if boxes:
        ax.boxplot(
            [g if len(g) else [np.nan] for g in groups],
            positions=positions,
            widths=width,
            showfliers=False,
            manage_ticks=False,
            patch_artist=True,
            boxprops={"facecolor": color, "alpha": 0.18, "edgecolor": color},
            medianprops={"color": color, "linewidth": 1.5},
            whiskerprops={"color": color},
            capprops={"color": color},
        )
    for pos, g in zip(positions, groups, strict=True):
        if not len(g):
            continue
        jitter = rng.uniform(-width / 3, width / 3, len(g)) if boxes else np.zeros(len(g))
        ax.scatter(
            pos + jitter,
            g,
            s=14,
            facecolors=face,
            edgecolors=color,
            linewidths=1,
            zorder=3,
            alpha=0.85,
        )
    means = np.array([g.mean() if len(g) else np.nan for g in groups])
    stds = np.array([g.std() if len(g) else np.nan for g in groups])
    ax.errorbar(
        positions,
        means,
        yerr=stds,
        fmt="D" if boxes else "D-",
        color=color,
        markerfacecolor=face,
        markeredgecolor=color,
        markersize=7,
        capsize=4,
        linewidth=2,
        zorder=4,
    )


def _draw_repeats(ax: Axes, m: _Metric) -> str:
    """Each side's repeats per swept point (or overall); returns the x label."""
    if m.base.swept:
        x = m.base.x
        groups = (list(m.base.points), list(m.cand.points))
        xlabel = m.base.swept[0]
        many = len(x) > _MAX_IMAGE_BOXES
        if many and all(_is_number(v) for v in x):
            positions = np.asarray(x, dtype=float)
            step = float(np.min(np.diff(np.sort(positions)))) if len(x) > 1 else 1.0
            offsets, width = (-step / 6, step / 6), step / 4
            ticks = None
        else:
            positions = np.arange(len(x), dtype=float)
            offsets, width = (-0.2, 0.2), 0.35
            ticks = (positions, list(_distinct([_label(v) for v in x])))
        boxes = not many
    else:
        groups = ([_finite_samples(m.base_da)], [_finite_samples(m.cand_da)])
        positions = np.array([0.0])
        offsets, width, boxes, xlabel = (-0.25, 0.25), 0.35, True, ""
        ticks = ([-0.25, 0.25], ["before", "after"])
    sides = ((_IMAGE_BEFORE_COLOR, False), (_IMAGE_AFTER_COLOR, True))
    for side_groups, offset, (color, filled) in zip(groups, offsets, sides, strict=True):
        _side_marks(ax, side_groups, positions + offset, color, filled, boxes=boxes, width=width)
    if ticks is not None:
        ax.set_xticks(*ticks)
        if len(ticks[1]) > 8:  # noqa: PLR2004 - past this, horizontal labels collide
            ax.tick_params(axis="x", labelrotation=45)
    return xlabel


def _heat_colors(direction: str) -> tuple[str, str, str]:
    """(color of a negative change, color of a positive change, what they mean)."""
    if direction == "minimize":
        return _IMAGE_BETTER, _IMAGE_WORSE, "blue = better (lower), red = worse"
    if direction == "maximize":
        return _IMAGE_WORSE, _IMAGE_BETTER, "blue = better (higher), red = worse"
    return _IMAGE_DOWN, _IMAGE_UP, "violet = down, yellow = up (no direction is set)"


def _render_heatmap_image(plan: Heatmap, metric: str) -> Figure:
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.figure import Figure

    down, up, meaning = _heat_colors(plan.direction)
    cmap = LinearSegmentedColormap.from_list("change", [down, _IMAGE_MID, up]).with_extremes(
        bad=_IMAGE_SURFACE
    )
    changes = [
        np.array(
            [
                [
                    np.nan if (p := _percent_change(b, a)) is None else p
                    for b, a in zip(br, ar, strict=True)
                ]
                for br, ar in zip(g.before, g.after, strict=True)
            ],
            dtype=float,
        )
        for g in plan.grids
    ]
    finite = np.concatenate([c[np.isfinite(c)] for c in changes]) if changes else np.array([])
    limit = max(float(np.abs(finite).max()) if finite.size else 0.0, 2 * plan.margin_percent, 1.0)
    n = len(plan.grids)
    cols = min(n, 3)
    rows = math.ceil(n / cols)
    width = min(4.0 + 4.0 * cols, 14.0)
    fig = Figure(figsize=(width, 1.4 + 3.6 * rows), dpi=100, facecolor=_IMAGE_SURFACE)
    axes = np.atleast_1d(fig.subplots(rows, cols, squeeze=False)).ravel()
    image = None
    for ax, grid, change in zip(axes, plan.grids, changes, strict=False):
        image = ax.imshow(change, cmap=cmap, vmin=-limit, vmax=limit, aspect="auto")
        ax.set_xticks(range(len(plan.col_labels)), plan.col_labels)
        ax.set_yticks(range(len(plan.row_labels)), plan.row_labels)
        ax.set_xlabel(plan.col_input, color=_IMAGE_MUTED_INK)
        ax.set_ylabel(plan.row_input, color=_IMAGE_MUTED_INK)
        ax.tick_params(colors=_IMAGE_MUTED_INK, labelsize=9)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if grid.layer is not None:
            ax.set_title(f"{plan.layer_input} = {grid.layer}", fontsize=10, color=_IMAGE_INK)
        if change.size <= _MAX_ANNOTATED_CELLS:
            for (r, c), value in np.ndenumerate(change):
                text = "n/a" if not math.isfinite(value) else _pct(value)
                # Light text on a strong color, dark text near the grey midpoint.
                strong = math.isfinite(value) and abs(value) > limit / 2
                ink = _IMAGE_SURFACE if strong else _IMAGE_INK
                ax.text(c, r, text, ha="center", va="center", fontsize=9, color=ink)
    for ax in axes[n:]:
        ax.set_visible(False)
    if image is not None:
        bar = fig.colorbar(image, ax=list(axes[:n]), shrink=0.85)
        bar.set_label(f"change % ({meaning})", color=_IMAGE_MUTED_INK)
        bar.ax.tick_params(colors=_IMAGE_MUTED_INK, labelsize=9)
    notes = f" · {' '.join(plan.notes)}" if plan.notes else ""
    fig.suptitle(
        f"{metric}: percent change before → after at each point{notes}",
        fontsize=11,
        color=_IMAGE_INK,
        wrap=True,
    )
    return fig


def _write_images(metrics: Sequence[_Metric], out_dir: Path) -> dict[str, Path]:
    """Write a PNG and a samples CSV for each metric an image adds to; ``{variable: png}``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pngs = {}
    for m in metrics:
        if not _image_adds_information(m):
            continue
        name = m.entry["variable"]
        png = out_dir / png_name(name)
        _render_png(m, png, detail=True)
        png.with_suffix(".csv").write_text(_samples_csv(m), encoding="utf-8")
        pngs[name] = png
    return pngs


@dataclass(frozen=True)
class EvidenceFiles:
    """What :func:`write_evidence` wrote; a path is None when its file was not asked for.

    ``pngs`` maps each metric to the PNG written for it: every metric with *png_dir*,
    else none; the Markdown links no PNG of ``pngs``. ``images`` maps each metric an
    image adds to (see *image_dir*) to its image, and ``image_urls`` maps each metric
    whose image the Markdown links to that link.
    """

    comparison: dict
    json_path: Path | None
    markdown_path: Path | None
    pngs: dict[str, Path]
    images: dict[str, Path] = field(default_factory=dict)
    image_urls: dict[str, str] = field(default_factory=dict)


def write_evidence(
    baseline: BenchResult,
    candidate: BenchResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    png_dir: str | Path | None = None,
    png_url_base: str | None = None,
    run_cfg: BenchRunCfg | None = None,
    image_dir: str | Path | None = None,
    publish_images: Callable[[dict[str, Path]], Mapping[str, str]] | None = None,
) -> EvidenceFiles:
    """Compare two results once and write the JSON, Markdown and PNGs asked for.

    The Markdown is text only and needs no PNG. PNGs are written only with
    *png_dir*, for local viewing. *png_url_base* is deprecated and ignored, with a
    :class:`DeprecationWarning`.

    With *image_dir*, each metric whose image shows more than its text chart (more
    than one sample at a point, or two or more swept inputs) also gets an image
    there: every repeat with a box per point and the mean ± 1 std, or a heatmap of
    the percent change. A ``<metric>.csv`` of every sample goes beside it.
    *publish_images* receives ``{file name: path}`` of those files and returns
    ``{file name: link}``; the Markdown puts each linked image above the metric's
    text chart, which stays. A file it does not link is left out of the Markdown.
    The images share the PNGs' file names, so *png_dir* and *image_dir* must differ
    (:class:`ValueError` otherwise).
    """
    if publish_images is not None and image_dir is None:
        raise ValueError("publish_images needs image_dir: the images are written there first")
    if (
        png_dir is not None
        and image_dir is not None
        and Path(png_dir).resolve() == Path(image_dir).resolve()
    ):
        raise ValueError(
            f"png_dir and image_dir are the same directory ({png_dir}): "
            "the images use the same file names and would overwrite the PNGs"
        )
    if png_url_base is not None:
        warnings.warn(PNG_URL_BASE_DEPRECATED, DeprecationWarning, stacklevel=2)
    comparison = compare_results(baseline, candidate, run_cfg=run_cfg)
    metrics = _metrics(baseline, candidate, comparison)

    written_json = None
    if json_path is not None:
        written_json = Path(json_path)
        written_json.parent.mkdir(parents=True, exist_ok=True)
        written_json.write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    pngs: dict[str, Path] = {}
    if png_dir is not None:
        pngs = {
            m.entry["variable"]: _render_png(m, Path(png_dir) / png_name(m.entry["variable"]))
            for m in metrics
        }

    images: dict[str, Path] = {}
    linked: dict[str, tuple[str, str | None]] = {}
    if image_dir is not None:
        images = _write_images(metrics, Path(image_dir))
        if publish_images is not None and images:
            files = {
                path.name: path
                for png in images.values()
                for path in (png, png.with_suffix(".csv"))
            }
            urls = publish_images(files)
            for name, png in images.items():
                if png.name in urls:
                    linked[name] = (urls[png.name], urls.get(png.with_suffix(".csv").name))

    written_md = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        written_md.write_text(_markdown(metrics, comparison, linked), encoding="utf-8")

    image_urls = {name: png_url for name, (png_url, _) in linked.items()}
    return EvidenceFiles(comparison, written_json, written_md, pngs, images, image_urls)
