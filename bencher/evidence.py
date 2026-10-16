"""PR-ready evidence from an A/B comparison: a Markdown block and PNG charts.

:func:`~bencher.report_export.compare_results` says *whether* a change moved each
metric. This module shows it: :func:`evidence_markdown` writes the block an agent
pastes as a pull request's ``## Evidence`` section, and :func:`write_evidence_pngs`
draws one chart per metric. :func:`write_evidence` writes any of the comparison
JSON, the Markdown and the PNGs in one call; ``bencher compare`` and ``bencher ab``
are its command-line front ends.

Each compared metric (both sides measured it) gets a chart and a caption. The
chart is a Mermaid ``xychart-beta`` when the metric fits one honestly -- no swept
input (one bar per side, for values that are not negative) or one numeric swept
input with the same values on both sides (two lines) -- a Markdown table for one
categorical swept input (string, enum or bool: a line between categories means
nothing), and an image link otherwise: two or more swept inputs, inputs that
differ between the sides, a negative value with no swept input (an xychart bar
grows from the axis bottom, not from 0), or a repeat-to-repeat spread as large as
the change, which only the PNG's ±std band can show.

``xychart-beta`` has no legend, so the title names the series by color: the grey
line is the baseline, the blue line is the candidate. Both colors are fixed in the
chart's front matter and read on GitHub's light and dark themes.

The caption gives the threshold verdict and the mean change, then the ``change``
record of :mod:`bencher.change_stats`: the mean difference, its bootstrap 95% CI
and the statistical verdict. With three or more compared metrics, one
``radar-beta`` chart above the per-metric charts shows every metric scaled so the
baseline mean is 1.
"""

from __future__ import annotations

import json
import math
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_never
from urllib.parse import quote

import numpy as np

from bencher.change_stats import IMPROVED, REGRESSED, TOO_FEW_SAMPLES, unpaired_change
from bencher.claims import Claim, Threshold, Within
from bencher.report_export import _snapshot_ds, compare_results

if TYPE_CHECKING:
    from collections.abc import Sequence

    import xarray as xr
    from matplotlib.axes import Axes

    from bencher.bench_cfg import BenchRunCfg
    from bencher.results.bench_result import BenchResult

# xychart-beta labels collide past this many points; longer numeric sweeps are binned.
MAX_CHART_POINTS = 30

# A y axis starts at 0 unless that squeezes the change below this share of the axis.
_MIN_CHANGE_SHARE_FROM_ZERO = 0.05

# Mermaid series colors: readable on GitHub's light and dark themes.
MERMAID_BEFORE_COLOR = "#9e9e9e"
MERMAID_AFTER_COLOR = "#2f81f7"

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
    """One numeric swept input shared by both sides: a grey line before, a blue line after."""

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
class ImageOnly:
    """The metric cannot be drawn honestly in xychart; ``reason`` says why."""

    reason: str


ChartPlan = BeforeAfterBars | SweepChart | CategoryTable | ImageOnly


def _is_number(value: Any) -> bool:
    """An int or float, but not a bool: a bool sweep is two categories."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _label(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _bin(
    x: tuple, before: np.ndarray, after: np.ndarray
) -> tuple[tuple[float, ...], np.ndarray, np.ndarray]:
    """Average consecutive points down to at most MAX_CHART_POINTS."""
    size = math.ceil(len(x) / MAX_CHART_POINTS)
    groups = [slice(i, i + size) for i in range(0, len(x), size)]
    centers = tuple(float(np.mean(np.asarray(x[g], dtype=float))) for g in groups)
    return (
        centers,
        np.array([np.nanmean(before[g]) for g in groups]),
        np.array([np.nanmean(after[g]) for g in groups]),
    )


def plan_chart(
    base: _Profile, cand: _Profile, *, direction: str = "none", margin_percent: float = 10.0
) -> ChartPlan:
    """Choose how a metric is shown: an xychart or table when that is honest, else an image.

    *direction* and *margin_percent* judge each row of a :class:`CategoryTable`.
    """
    if base.swept != cand.swept:
        return ImageOnly("the sides swept different inputs")
    if len(base.swept) > 1:
        return ImageOnly(f"{len(base.swept)} swept inputs")
    if not np.isfinite(base.mean).all() or not np.isfinite(cand.mean).all():
        return ImageOnly("some points have no recorded sample")
    noise = float(max(base.std.max(), cand.std.max()))
    change = float(np.max(np.abs(cand.mean - base.mean))) if base.x == cand.x else math.inf
    if noise > 0 and noise >= change:
        return ImageOnly("the spread between repeats is as large as the change")
    if not base.swept:
        before, after = float(base.mean[0]), float(cand.mean[0])
        if min(before, after) < 0:
            return ImageOnly("an xychart bar for a negative value grows from the axis bottom")
        return BeforeAfterBars(before, after)
    if base.x != cand.x:
        return ImageOnly(f"the sides swept different values of {base.swept[0]}")
    x, before, after = base.x, base.mean, cand.mean
    numeric = all(_is_number(v) for v in x)
    if len(x) > MAX_CHART_POINTS:
        if not numeric:
            return ImageOnly(f"{len(x)} categories of {base.swept[0]}")
        x, before, after = _bin(x, before, after)
    if not numeric:
        labels = tuple(_label(v) for v in x)
        if len(set(labels)) < len(labels):
            return ImageOnly(f"the values of {base.swept[0]} do not print as distinct labels")
        return CategoryTable(
            base.swept[0],
            tuple(
                CategoryRow(
                    label, float(b), float(c), unpaired_change(bp, cp, direction, margin_percent)
                )
                for label, b, c, bp, cp in zip(
                    labels, before, after, base.points, cand.points, strict=True
                )
            ),
        )
    if any(isinstance(v, float) for v in x):
        labels = tuple(_chart_nums([float(v) for v in x]))
    else:
        labels = tuple(_label(v) for v in x)
    if len(set(labels)) < len(labels):
        return ImageOnly(f"the values of {base.swept[0]} do not print as distinct labels")
    return SweepChart(
        base.swept[0],
        labels,
        tuple(float(v) for v in before),
        tuple(float(v) for v in after),
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


def mermaid_chart(
    name: str, units: str | None, plan: BeforeAfterBars | SweepChart, claim: Claim | None
) -> str:
    """The fenced ``xychart-beta`` block for a plan that has one."""
    metric = _mermaid_text(f"{name} ({units})" if units else name)
    match plan:
        case BeforeAfterBars(before=before, after=after):
            title = f"{metric}: before vs after"
            x_axis = 'x-axis ["before", "after"]'
            lo, hi, step = _y_range([before], [after], claim)
            series = [f"bar [{', '.join(_chart_nums([before, after]))}]"]
            front_matter = []
        case SweepChart(input_name=input_name, labels=labels, before=before, after=after):
            title = f"{metric}: grey = before, blue = after"
            quoted = ", ".join(f'"{_mermaid_text(label)}"' for label in labels)
            x_axis = f'x-axis "{_mermaid_text(input_name)}" [{quoted}]'
            lo, hi, step = _y_range(before, after, claim)
            text = _chart_nums([*before, *after])
            series = [
                f"line [{', '.join(text[: len(before)])}]",
                f"line [{', '.join(text[len(before) :])}]",
            ]
            front_matter = [
                "---",
                "config:",
                "  themeVariables:",
                "    xyChart:",
                f'      plotColorPalette: "{MERMAID_BEFORE_COLOR}, {MERMAID_AFTER_COLOR}"',
                "---",
            ]
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
        "  themeVariables:",
        f'    cScale0: "{MERMAID_BEFORE_COLOR}"',
        f'    cScale1: "{MERMAID_AFTER_COLOR}"',
        "---",
        "radar-beta",
        "  title Metrics relative to before (before = 1)",
        f"  axis {labels}",
        f'  curve before["before"]{{{", ".join([one] * len(axes))}}}',
        f'  curve after["after"]{{{", ".join(after)}}}',
        f"  max {_num(top)}",
        "  min 0",
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
_DIRECTED = (IMPROVED, REGRESSED)


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
    if threshold != verdict and (threshold in _DIRECTED or verdict in _DIRECTED):
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
            )
        )
    return out


def _image_link(name: str, png_url_base: str | None) -> str:
    if png_url_base is None or png_url_base == "":
        return name
    return f"{png_url_base.rstrip('/')}/{name}"


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


def _markdown(metrics: list[_Metric], comparison: dict, png_url_base: str | None) -> str:
    blocks = [_summary(comparison)]
    blocks += [b for b in (_claims_block(comparison), _unpaired_block(comparison)) if b]
    if (radar := radar_chart([m.entry for m in metrics])) is not None:
        blocks.append(radar)
    for m in metrics:
        name = m.entry["variable"]
        match m.plan:
            case BeforeAfterBars() | SweepChart():
                chart = mermaid_chart(name, m.units, m.plan, m.claim)
            case CategoryTable():
                chart = category_table(name, m.units, m.plan)
            case ImageOnly():
                link = _image_link(png_name(name), png_url_base)
                chart = f"![{name}: before vs after]({link})"
            case _ as unreachable:
                assert_never(unreachable)
        blocks.append(
            chart + "\n\n" + caption(m.entry, m.units, comparison, (m.base.samples, m.cand.samples))
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
    """Markdown for a PR's ``## Evidence`` section: a chart and caption per metric.

    Above the charts, a **Claims** list judges every claim the candidate declares,
    with "no baseline" for a metric the baseline does not measure, and a **Not
    compared** list names each metric only one side declares.

    Args:
        baseline: The result before the change.
        candidate: The result after the change.
        comparison: A :func:`compare_results` dict for the pair, when already computed.
        png_url_base: Prefix for the image links of metrics that need a PNG (for
            example a pinned raw URL the PNGs were pushed to). Without it a link is
            the bare file name, relative to the Markdown file.
        run_cfg: Forwarded to :func:`compare_results` when *comparison* is omitted.
    """
    if comparison is None:
        comparison = compare_results(baseline, candidate, run_cfg=run_cfg)
    return _markdown(_metrics(baseline, candidate, comparison), comparison, png_url_base)


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


def _render_png(m: _Metric, path: Path) -> Path:
    # Figure without pyplot: no global backend state, safe in any process.
    from matplotlib.figure import Figure

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


@dataclass(frozen=True)
class EvidenceFiles:
    """What :func:`write_evidence` wrote; a path is None when its file was not asked for.

    ``pngs`` maps each metric to the PNG written for it: every metric with *png_dir*,
    else only the metrics whose Markdown links an image.
    """

    comparison: dict
    json_path: Path | None
    markdown_path: Path | None
    pngs: dict[str, Path]


def write_evidence(
    baseline: BenchResult,
    candidate: BenchResult,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    png_dir: str | Path | None = None,
    png_url_base: str | None = None,
    run_cfg: BenchRunCfg | None = None,
) -> EvidenceFiles:
    """Compare two results once and write the JSON, Markdown and PNGs asked for.

    Markdown that links a PNG needs the PNG to exist: when *png_dir* is not given,
    the PNGs the Markdown links are written next to the Markdown file. Without
    *png_url_base*, links are relative to the Markdown file.
    """
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

    written_md = None
    if markdown_path is not None:
        written_md = Path(markdown_path)
        written_md.parent.mkdir(parents=True, exist_ok=True)
        image_dir = Path(png_dir) if png_dir is not None else written_md.parent
        for m in metrics:
            name = m.entry["variable"]
            if isinstance(m.plan, ImageOnly) and name not in pngs:
                pngs[name] = _render_png(m, image_dir / png_name(name))
        base = png_url_base or None
        if base is None:
            rel = os.path.relpath(image_dir.resolve(), written_md.parent.resolve())
            base = "" if rel == "." else quote(rel.replace(os.sep, "/"))
        written_md.write_text(_markdown(metrics, comparison, base), encoding="utf-8")

    return EvidenceFiles(comparison, written_json, written_md, pngs)
