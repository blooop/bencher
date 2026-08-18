"""Pure data-shaping for the scorecard: summary dicts -> table cells.

No filesystem and no templating here — every function takes already-parsed
summary records (the :func:`~bencher.report_export.result_to_dict` contract,
with per-metric ``series``) and returns plain dicts the renderer turns into
HTML. This keeps the column/verdict/formatting logic unit-testable in isolation.
"""

from __future__ import annotations

import math

from bencher.report_export import _verdict as _core_verdict
from bencher.scorecard.config import ScorecardConfig
from bencher.sparkline import sparkline_svg


def unify_metric_names(
    metrics: dict[str, dict], regressions: dict[str, dict], aliases: dict[str, str]
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Apply *aliases* to one benchmark's metrics + regressions.

    Returns new dicts keyed by canonical column names, preserving metric order.
    A renamed metric records its original name under ``source_variable`` so a
    cell tooltip can surface it. Collisions (the canonical name already exists on
    this benchmark, or two of its metrics map to the same alias) keep the raw
    name to never drop or shadow data.
    """
    unified: dict[str, dict] = {}
    unified_regs: dict[str, dict] = {}
    for var, metric in metrics.items():
        canonical = aliases.get(var)
        if canonical is None or canonical in metrics or canonical in unified:
            key = var
        else:
            key = canonical
        entry = dict(metric)
        if key != var:
            entry["source_variable"] = var
        unified[key] = entry
        if var in regressions:
            unified_regs[key] = regressions[var]
    # Regression entries without a matching metric pass through untouched.
    for var, reg in regressions.items():
        if var not in metrics:
            unified_regs.setdefault(var, reg)
    return unified, unified_regs


def metric_columns(records: list[dict]) -> list[str]:
    """Union of metric names, ordered by (shared-by-most, first-seen)."""
    first_seen: dict[str, int] = {}
    counts: dict[str, int] = {}
    for idx, rec in enumerate(records):
        for var in rec["metrics"]:
            first_seen.setdefault(var, idx * 1000 + len(first_seen))
            counts[var] = counts.get(var, 0) + 1
    return sorted(counts, key=lambda v: (-counts[v], first_seen[v]))


def _unit_label(units: str | None) -> str:
    """Displayable unit, or ``""`` for the unitless sentinels a value drops."""
    return units if units and units not in ("", "ratio") else ""


def column_units(
    records: list[dict], columns: list[str], config: ScorecardConfig
) -> dict[str, str]:
    """Header unit per column, or ``""`` when it has to stay on the values.

    A unit is hoisted to the header only when every benchmark reporting that
    column declares the same non-empty one, so hoisting can never relabel a
    neighbour's value: a column mixing ``m`` with ``mm`` (or one bench leaving
    it unitless) keeps its units in the cells. A percent metric is always
    ``%`` — the fraction renders as a percentage whatever units it recorded.
    """
    units: dict[str, str] = {}
    for var in columns:
        if var in config.percent_metrics:
            units[var] = "%"
            continue
        declared = {
            _unit_label(rec["metrics"][var].get("units"))
            for rec in records
            if var in rec["metrics"]
        }
        units[var] = next(iter(declared)) if len(declared) == 1 else ""
    return units


def cell_verdict(reg: dict | None) -> str:
    """4-way display verdict for a cell.

    ``None`` — no regression gate on this metric (or too little history) — maps
    to the uncolored ``"trend"`` fallback. A gate on a *young baseline* maps
    there too: the baseline is younger than ``regression_min_history``, so
    bencher reports the regression but never blocks on it — colouring it like a
    real regression would overstate a verdict its own gate treats as advisory.
    Otherwise defer to bencher's 3-state core verdict (method-aware: it
    measures the improvement in the record's own threshold units) and render
    its ``"unchanged"`` as ``"passed"`` (the gate ran and did not flag). A gate
    with no threshold can only have "passed".
    """
    if reg is None:
        return "trend"
    if reg.get("young_baseline"):
        return "trend"
    if bool(reg.get("regressed")):
        return "regressed"
    threshold = reg.get("threshold")
    if threshold is None:
        return "passed"
    # reg["regressed"] is falsy past the guard above, so _core_verdict can never
    # return "regressed" here — it only decides improved vs unchanged.
    core = _core_verdict(reg)
    return "passed" if core == "unchanged" else core


def fmt_value(
    value: float | None,
    units: str | None,
    *,
    as_percent: bool = False,
    with_units: bool = True,
) -> str:
    """Compact human label for a scalar value (``—`` when missing).

    ``with_units=False`` drops the unit suffix (including the ``%`` of a
    percentage) for a caller that shows the unit once in the column header
    instead of on every value.
    """
    if value is None or not math.isfinite(value):
        return "—"
    if as_percent:
        # 0..1 fraction rendered as a percentage ("95%" rather than "0.95").
        text = f"{value * 100:.4g}"
        return f"{text}%" if with_units else text
    text = f"{value:.4g}"
    label = _unit_label(units)
    if label and with_units:
        text = f"{text} {label}"
    return text


def fmt_change(change_percent: float | None) -> str:
    """Signed percent label for a Δ (empty when not computable)."""
    if change_percent is None or not math.isfinite(change_percent):
        return ""
    return f"{change_percent:+.1f}%"


def build_cell(
    rec: dict, var: str, config: ScorecardConfig, *, units_in_header: bool = False
) -> dict | None:
    """Build one table cell for (benchmark, metric), or None when absent.

    A cell shows one number — the latest value — plus its Δ; μ, σ, the baseline
    and the run count go to the tooltip, because a column is only as wide as the
    table divided by its columns and four labelled numbers do not fit in one.
    Set ``units_in_header`` when the caller shows the column's unit once in the
    header (see :func:`column_units`), so the value drops its own suffix.
    """
    metric = rec["metrics"].get(var)
    if metric is None:
        return None
    units = metric.get("units")
    as_percent = var in config.percent_metrics
    series = metric.get("series") or []
    means = [pt.get("mean") for pt in series]
    stds = [pt.get("std") for pt in series]
    finite = [m for m in means if m is not None and math.isfinite(m)]
    latest = finite[-1] if finite else metric.get("optimal_value")
    prev = finite[-2] if len(finite) >= 2 else None
    mean_val = sum(finite) / len(finite) if finite else None
    # σ over the per-event means: the spread of the dots in the distribution
    # column that μ summarises (population std, so a lone run reads 0).
    std_val = math.sqrt(sum((x - mean_val) ** 2 for x in finite) / len(finite)) if finite else None
    reg = rec["regressions"].get(var)

    verdict = cell_verdict(reg)
    if reg is not None:
        # Gated: use bencher's threshold-aware verdict + reported baseline/delta.
        change_str = fmt_change(reg.get("change_percent"))
        baseline_str = fmt_value(reg.get("baseline_value"), units, as_percent=as_percent)
    else:
        # No regression gate (or <2 over-time events yet): still surface the
        # trend. Show a neutral latest-vs-previous delta from the series itself;
        # the ±std band shows whether a move exceeds the run-to-run noise.
        change_str = ""
        baseline_str = ""
        if prev:
            baseline_str = fmt_value(prev, units, as_percent=as_percent)
            change_str = fmt_change((latest - prev) / abs(prev) * 100.0)

    mean_str = fmt_value(mean_val, units, as_percent=as_percent)
    std_str = fmt_value(std_val, units, as_percent=as_percent)
    tooltip_parts = [var]
    if metric.get("source_variable"):
        tooltip_parts.append(f"variable: {metric['source_variable']}")
    if mean_val is not None and math.isfinite(mean_val):
        tooltip_parts.append(f"μ {mean_str} · σ {std_str}")
    if baseline_str:
        tooltip_parts.append(f"baseline {baseline_str} · {len(finite)} runs")
    return {
        "verdict": verdict,
        "latest_str": fmt_value(
            latest, units, as_percent=as_percent, with_units=not units_in_header
        ),
        "mean_str": mean_str,
        "std_str": std_str,
        "change_str": change_str,
        "baseline_str": baseline_str,
        "n_events": len(finite),
        "tooltip": " · ".join(tooltip_parts),
        "svg": sparkline_svg(means, stds),
    }
