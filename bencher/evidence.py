"""PR-ready evidence from an A/B comparison: a Markdown block and PNG charts.

:func:`~bencher.report_export.compare_results` says *whether* a change moved each
metric. This module shows it: :func:`evidence_markdown` writes the block an agent
pastes as a pull request's ``## Evidence`` section, and :func:`write_evidence_pngs`
draws one chart per metric. :func:`write_evidence` writes any of the comparison
JSON, the Markdown and the PNGs in one call; ``bencher compare`` and ``bencher ab``
are its command-line front ends.

Each metric gets a chart and a caption. The chart is a Mermaid ``xychart-beta``
when the metric fits one honestly -- no swept input (one bar per side) or one swept
input with the same values on both sides -- and an image link otherwise: two or more
swept inputs, inputs that differ between the sides, or a repeat-to-repeat spread as
large as the change, which only the PNG's ±std band can show.

``xychart-beta`` has no legend, so the title names the series: bars are the
baseline, the line is the candidate.
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

import numpy as np

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
    return _Profile(
        swept=swept,
        x=x,
        mean=np.atleast_1d(np.asarray(mean.values, dtype=float)),
        std=np.atleast_1d(np.nan_to_num(np.asarray(std.values, dtype=float))),
        samples=int(values.notnull().sum()),
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
    """One swept input shared by both sides: bars before, line after."""

    input_name: str
    labels: tuple[str, ...]
    before: tuple[float, ...]
    after: tuple[float, ...]


@dataclass(frozen=True)
class ImageOnly:
    """The metric cannot be drawn honestly in xychart; ``reason`` says why."""

    reason: str


ChartPlan = BeforeAfterBars | SweepChart | ImageOnly


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


def plan_chart(base: _Profile, cand: _Profile) -> ChartPlan:
    """Choose how a metric is shown: an xychart when that is honest, else an image."""
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
        return BeforeAfterBars(float(base.mean[0]), float(cand.mean[0]))
    if base.x != cand.x:
        return ImageOnly(f"the sides swept different values of {base.swept[0]}")
    x, before, after = base.x, base.mean, cand.mean
    if len(x) > MAX_CHART_POINTS:
        if not all(isinstance(v, (int, float)) for v in x):
            return ImageOnly(f"{len(x)} categories of {base.swept[0]}")
        x, before, after = _bin(x, before, after)
    return SweepChart(
        base.swept[0],
        tuple(_label(v) for v in x),
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
) -> tuple[float, float]:
    """A y range holding both series and the claim, from 0 unless 0 hides the change."""
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
    return math.floor(lo / step) * step, math.ceil(hi / step) * step


def _num(value: float) -> str:
    return f"{value:.4g}"


def _chart_num(value: float, digits: int = 4) -> str:
    """A number xychart parses: positional, since its grammar has no exponent (1e+05)."""
    return np.format_float_positional(
        value, precision=digits, unique=False, fractional=False, trim="-"
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
            lo, hi = _y_range([before], [after], claim)
            series = [f"bar [{_chart_num(before)}, {_chart_num(after)}]"]
        case SweepChart(input_name=input_name, labels=labels, before=before, after=after):
            title = f"{metric}: bars = before, line = after"
            quoted = ", ".join(f'"{_mermaid_text(label)}"' for label in labels)
            x_axis = f'x-axis "{_mermaid_text(input_name)}" [{quoted}]'
            lo, hi = _y_range(before, after, claim)
            series = [
                f"bar [{', '.join(_chart_num(v) for v in before)}]",
                f"line [{', '.join(_chart_num(v) for v in after)}]",
            ]
        case _ as unreachable:
            assert_never(unreachable)
    lines = [
        "```mermaid",
        "xychart-beta",
        f'    title "{title}"',
        f"    {x_axis}",
        f'    y-axis "{metric}" {_chart_num(lo, 6)} --> {_chart_num(hi, 6)}',
        *(f"    {s}" for s in series),
        "```",
    ]
    return "\n".join(lines)


# --- captions --------------------------------------------------------------------


def _where(inputs: dict) -> str:
    return ", ".join(f"{k}={_label(v)}" for k, v in inputs.items())


def _claim_side(side: dict) -> str:
    if side["holds"] is None:
        return "not measured"
    verdict = "holds" if side["holds"] else "fails"
    worst = side["worst_value"]
    worst_text = "inf" if worst is None else _num(worst)
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
    provenance = (
        f"<sub>baseline {_revision(comparison['baseline'])}, {samples[0]} samples · "
        f"candidate {_revision(comparison['candidate'])}, {samples[1]} samples</sub>"
    )
    return " · ".join(parts) + "  \n" + provenance


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
        out.append(
            _Metric(
                entry=entry,
                units=getattr(rv, "units", None),
                claim=getattr(rv, "claim", None),
                base=base,
                cand=cand,
                plan=plan_chart(base, cand),
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


def _markdown(metrics: list[_Metric], comparison: dict, png_url_base: str | None) -> str:
    blocks = [_summary(comparison)]
    for m in metrics:
        name = m.entry["variable"]
        match m.plan:
            case BeforeAfterBars() | SweepChart():
                chart = mermaid_chart(name, m.units, m.plan, m.claim)
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


def _draw(ax: Axes, m: _Metric) -> None:
    base, cand = m.base, m.cand
    if not base.swept and not cand.swept:
        ax.bar(
            [0, 1],
            [base.mean[0], cand.mean[0]],
            yerr=[base.std[0], cand.std[0]],
            color=[_BEFORE_COLOR, _AFTER_COLOR],
            capsize=6,
            width=0.5,
        )
        ax.set_xticks([0, 1], ["before", "after"])
        return
    numeric = all(isinstance(v, (int, float)) for v in base.x + cand.x)
    for profile, label, color, style in (
        (base, "before", _BEFORE_COLOR, "--"),
        (cand, "after", _AFTER_COLOR, "-"),
    ):
        if not profile.swept:
            # One value across the other side's sweep: a level line with its band.
            mean, std = profile.mean[0], profile.std[0]
            ax.axhline(mean, linestyle=style, color=color, label=label, linewidth=2)
            ax.axhspan(mean - std, mean + std, color=color, alpha=0.18)
            continue
        if numeric:
            x = np.asarray(profile.x, dtype=float)
        else:
            categories = list(dict.fromkeys(base.x + cand.x))
            x = np.array([categories.index(v) for v in profile.x], dtype=float)
            ax.set_xticks(range(len(categories)), [_label(c) for c in categories])
        ax.plot(x, profile.mean, style, marker="o", color=color, label=label, linewidth=2)
        ax.fill_between(
            x, profile.mean - profile.std, profile.mean + profile.std, color=color, alpha=0.18
        )
    ax.set_xlabel(base.swept[0] if base.swept else cand.swept[0])


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
    ax = fig.add_subplot()
    _draw(ax, m)
    _draw_claim(ax, m.claim)
    swept = m.base.swept if len(m.base.swept) >= len(m.cand.swept) else m.cand.swept
    rest = f", mean over {', '.join(swept[1:])}" if len(swept) > 1 else ""
    metric = f"{name} ({m.units})" if m.units else name
    spread = "band" if swept else "error bar"
    ax.set_title(f"{metric}: before (grey) vs after (blue), {spread} = ±1 std{rest}", fontsize=12)
    ax.set_ylabel(metric)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", frameon=False)
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
    """What :func:`write_evidence` wrote; a field is None (or empty) when not asked for."""

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
        base = png_url_base
        if base is None:
            rel = os.path.relpath(image_dir.resolve(), written_md.parent.resolve())
            base = "" if rel == "." else rel.replace(os.sep, "/")
        written_md.write_text(_markdown(metrics, comparison, base), encoding="utf-8")

    return EvidenceFiles(comparison, written_json, written_md, pngs)
