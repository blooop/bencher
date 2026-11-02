"""Improved / regressed / unchanged verdicts read from a regression record.

The verdict reads a plain mapping -- the
:meth:`~bencher.regression.RegressionResult.to_dict` contract, or a record parsed
back from a ``*.summary.json`` -- so it needs nothing but the standard library. It
lives apart from :mod:`bencher.report_export` (which loads numpy, xarray and param)
so that :mod:`bencher.scorecard` can classify cells without importing the
numerical stack. :mod:`bencher.report_export` re-exports every name here.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# The values of ``OptDir.minimize`` / ``OptDir.maximize`` (bencher.variables.results).
# Spelled out rather than imported because that module loads param; a test pins them
# to the enum.
_MINIMIZE = "minimize"
_MAXIMIZE = "maximize"


def _finite_value(value: object) -> float | None:
    """Coerce *value* to a finite float, or None for anything that isn't one.

    The tolerant *reader* counterpart to
    :func:`~bencher.regression._finite_or_none` (the strict *writer* used by
    ``to_dict``): this one is fed records parsed from ``*.summary.json`` files
    that bencher may not have written, so every non-numeric, non-finite, or
    unrepresentable input degrades to ``None`` (which the verdict branches treat
    as "abstain") rather than aborting a scorecard build. ``OverflowError``
    matters in particular because JSON integers are arbitrary-precision, so a
    hand-edited or foreign summary can carry an int too large for a float.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _verdict(reg: Mapping[str, object]) -> str:
    """Classify a metric movement as improved / regressed / unchanged.

    *reg* follows the :meth:`~bencher.regression.RegressionResult.to_dict`
    contract. ``regressed`` comes straight from the detector (direction- and
    threshold-aware). An improvement is the mirror image — a beneficial-direction
    move that clears the detector's gate — measured in each method's own units,
    because ``threshold`` means percent, absolute delta, MAD-sigma, or an
    absolute limit depending on ``method``:

    * ``percentage`` (and unknown methods, mirroring the fallback in
      :func:`~bencher.regression.method_cells`): ``|change_percent|`` clears
      ``threshold`` (a percent).
    * ``delta``: ``|current_value - baseline_value|`` clears ``threshold``
      (absolute units).
    * ``adaptive``: ``current_value`` lies outside the MAD acceptance band
      (``band_lower``/``band_upper``) and, when the dual-band percent gate is
      present, outside ``percent_band_lower``/``percent_band_upper`` too —
      mirroring :func:`~bencher.regression.detect_adaptive`'s AND gate.
      Abstains to "unchanged" when the bands are absent from the record.
    * ``absolute``: a fixed limit with no baseline to improve against
      (``change_percent`` is always NaN/None), so a non-regressed check is
      explicitly "unchanged".
    """
    if reg.get("regressed"):
        return "regressed"
    method = reg.get("method")
    if method == "absolute":
        improved = False
    elif method == "delta":
        improved = _delta_improved(reg)
    elif method == "adaptive":
        improved = _adaptive_improved(reg)
    else:
        improved = _percent_improved(reg)
    return "improved" if improved else "unchanged"


def _beneficial(delta: float, direction: object) -> bool:
    """True when a signed movement is in the variable's beneficial direction."""
    return (direction == _MINIMIZE and delta < 0) or (direction == _MAXIMIZE and delta > 0)


def _delta_improved(reg: Mapping[str, object]) -> bool:
    """Delta method: gate the improvement on |current - baseline| in absolute units.

    Strict ``>`` to mirror :func:`~bencher.regression.detect_delta`'s
    ``delta > max_delta`` exactly (contrast :func:`_percent_improved`, which keeps
    the pre-existing inclusive convention).
    """
    current = _finite_value(reg.get("current_value"))
    baseline = _finite_value(reg.get("baseline_value"))
    threshold = _finite_value(reg.get("threshold"))
    if current is None or baseline is None or threshold is None:
        return False
    delta = current - baseline
    return _beneficial(delta, reg.get("direction")) and abs(delta) > threshold


def _adaptive_improved(reg: Mapping[str, object]) -> bool:
    """Adaptive method: improved iff outside the MAD band (and any percent band)."""
    current = _finite_value(reg.get("current_value"))
    baseline = _finite_value(reg.get("baseline_value"))
    band_lower = _finite_value(reg.get("band_lower"))
    band_upper = _finite_value(reg.get("band_upper"))
    if current is None or baseline is None or band_lower is None or band_upper is None:
        return False  # bands absent from the record: abstain.
    if not _beneficial(current - baseline, reg.get("direction")):
        return False
    if band_lower <= current <= band_upper:
        return False
    # Dual-band AND gate: when the percent band is present, being inside it suppresses.
    pct_lower = _finite_value(reg.get("percent_band_lower"))
    pct_upper = _finite_value(reg.get("percent_band_upper"))
    if pct_lower is None or pct_upper is None:
        return True
    # detect_adaptive derives the band as baseline*(1 ± pct/100), which INVERTS the
    # endpoints for a negative baseline (baseline=-100, pct=5 -> (-95, -105)); sort so
    # the membership test still holds there. The detector itself is unaffected because
    # it gates on _safe_change_percent, which divides by abs(baseline).
    pct_lower, pct_upper = sorted((pct_lower, pct_upper))
    return not pct_lower <= current <= pct_upper


def _percent_improved(reg: Mapping[str, object]) -> bool:
    """Percentage method (and unknown-method fallback, mirroring method_cells)."""
    change_percent = _finite_value(reg.get("change_percent"))
    threshold = _finite_value(reg.get("threshold"))
    if change_percent is None or threshold is None:
        return False
    return _beneficial(change_percent, reg.get("direction")) and abs(change_percent) >= threshold
