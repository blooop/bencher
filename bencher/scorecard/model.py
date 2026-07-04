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


def cell_verdict(reg: dict | None) -> str:
    """4-way display verdict for a cell.

    ``None`` — no regression gate on this metric (or too little history) — maps
    to the uncolored ``"trend"`` fallback. Otherwise defer to bencher's 3-state
    core verdict and render its ``"unchanged"`` as ``"passed"`` (the gate ran and
    did not flag). A gate with no threshold can only have "passed".
    """
    if reg is None:
        return "trend"
    if bool(reg.get("regressed")):
        return "regressed"
    threshold = reg.get("threshold")
    if threshold is None:
        return "passed"
    core = _core_verdict(reg.get("change_percent"), reg.get("direction", "none"), False, threshold)
    return "passed" if core == "unchanged" else core


def fmt_value(value: float | None, units: str | None, *, as_percent: bool = False) -> str:
    """Compact human label for a scalar value (``—`` when missing)."""
    if value is None or not math.isfinite(value):
        return "—"
    if as_percent:
        # 0..1 fraction rendered as a percentage ("95%" rather than "0.95").
        return f"{value * 100:.4g}%"
    text = f"{value:.4g}"
    if units and units not in ("", "ratio"):
        text = f"{text} {units}"
    return text


def fmt_change(change_percent: float | None) -> str:
    """Signed percent label for a Δ (empty when not computable)."""
    if change_percent is None or not math.isfinite(change_percent):
        return ""
    return f"{change_percent:+.1f}%"


def build_cell(rec: dict, var: str, config: ScorecardConfig) -> dict | None:
    """Build one table cell for (benchmark, metric), or None when absent."""
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
    tooltip_parts = []
    if metric.get("source_variable"):
        tooltip_parts.append(f"variable: {metric['source_variable']}")
    if mean_val is not None and math.isfinite(mean_val):
        tooltip_parts.append(f"μ {mean_str}")
    if baseline_str:
        tooltip_parts.append(f"baseline {baseline_str} · {len(finite)} runs")
    return {
        "verdict": verdict,
        "latest_str": fmt_value(latest, units, as_percent=as_percent),
        "mean_str": mean_str,
        "change_str": change_str,
        "baseline_str": baseline_str,
        "n_events": len(finite),
        "tooltip": " · ".join(tooltip_parts),
        "svg": sparkline_svg(means, stds),
    }
