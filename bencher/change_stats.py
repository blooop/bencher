"""How much a change moved a metric: the mean difference with a bootstrap 95% CI.

:func:`~bencher.report_export.compare_results` attaches one :func:`change_between`
record to each compared metric, under the ``change`` key. The record is separate
from the metric's threshold ``verdict``; it says whether the data support a
change at all.

* **Paired** (``"paired_bootstrap"``): when both sides swept the same inputs, each
  input point is reduced to its mean over repeats and the per-point difference
  (candidate - baseline) is bootstrapped. Pairing removes the spread that comes
  from the sweep itself.
* **Unpaired** (``"bootstrap"``): with no swept input the samples are repeats, and
  the difference of the two means is bootstrapped, each side resampled on its own.

The CI is the 2.5th to 97.5th percentile of :data:`RESAMPLES` bootstrap means drawn
with a fixed seed, so the same data give the same record every time.

``stat_verdict`` reads the CI against 0 and against an equivalence margin of
``±equivalence_percent`` of the baseline mean (the comparison's
``regression_percentage``, 10% by default):

* ``"equivalent within ±X%"`` -- the whole CI lies inside the margin (a TOST-style
  equivalence test), even when it excludes 0: the change is too small to matter.
* ``"improved"`` / ``"regressed"`` -- the CI excludes 0, in the result variable's
  better / worse direction; ``"increased"`` / ``"decreased"`` for a variable with
  no direction.
* ``"no significant change"`` -- the CI holds 0 and reaches past the margin.
* ``"too few samples"`` -- fewer than :data:`MIN_SAMPLES` finite points (paired)
  or samples on a side (unpaired): no CI is given.
* ``"not comparable"`` -- the sides swept different inputs or share no input point;
  ``reason`` says which.

Numpy only, so it works on a light install.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import xarray as xr

CI_LEVEL = 0.95
RESAMPLES = 10_000
# A CI needs at least this many finite points (paired) or samples per side (unpaired).
MIN_SAMPLES = 2
SEED = 20_261_016

IMPROVED = "improved"
REGRESSED = "regressed"
INCREASED = "increased"
DECREASED = "decreased"
NO_SIGNIFICANT_CHANGE = "no significant change"
EQUIVALENT = "equivalent within"
TOO_FEW_SAMPLES = "too few samples"
NOT_COMPARABLE = "not comparable"

# Index arrays above this many entries are drawn in chunks, to bound memory.
_CHUNK_ENTRIES = 2_000_000


def _finite(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float).ravel()
    return values[np.isfinite(values)]


def _bootstrap_means(rng: np.random.Generator, values: np.ndarray) -> np.ndarray:
    """:data:`RESAMPLES` means of *values* resampled with replacement."""
    out = np.empty(RESAMPLES)
    chunk = max(1, _CHUNK_ENTRIES // len(values))
    for start in range(0, RESAMPLES, chunk):
        stop = min(RESAMPLES, start + chunk)
        idx = rng.integers(0, len(values), size=(stop - start, len(values)))
        out[start:stop] = values[idx].mean(axis=1)
    return out


def _percentile_ci(diffs: np.ndarray) -> tuple[float, float]:
    tail = (1.0 - CI_LEVEL) / 2.0 * 100.0
    low, high = np.percentile(diffs, [tail, 100.0 - tail])
    return float(low), float(high)


def stat_verdict(
    ci_low: float, ci_high: float, baseline_mean: float, direction: str, margin_percent: float
) -> str:
    """Read a CI of (candidate - baseline) against 0 and the equivalence margin."""
    margin = abs(baseline_mean) * margin_percent / 100.0
    if margin > 0 and -margin <= ci_low and ci_high <= margin:
        return f"{EQUIVALENT} ±{margin_percent:g}%"
    if ci_low <= 0.0 <= ci_high:
        return NO_SIGNIFICANT_CHANGE
    rose = ci_low > 0.0
    if direction == "minimize":
        return REGRESSED if rose else IMPROVED
    if direction == "maximize":
        return IMPROVED if rose else REGRESSED
    return INCREASED if rose else DECREASED


def _record(
    *,
    method: str | None,
    n: int,
    n_baseline: int,
    n_candidate: int,
    mean_diff: float | None,
    ci: tuple[float, float] | None,
    verdict: str,
    margin_percent: float,
    reason: str | None = None,
) -> dict:
    record = {
        "mean_diff": mean_diff,
        "ci_low": None if ci is None else ci[0],
        "ci_high": None if ci is None else ci[1],
        "ci_level": CI_LEVEL,
        "method": method,
        "n": n,
        "n_baseline": n_baseline,
        "n_candidate": n_candidate,
        "resamples": RESAMPLES if ci is not None else 0,
        "equivalence_percent": margin_percent,
        "stat_verdict": verdict,
    }
    if reason is not None:
        record["reason"] = reason
    return record


def paired_change(
    before: np.ndarray, after: np.ndarray, direction: str, margin_percent: float
) -> dict:
    """Bootstrap the mean of per-point differences ``after - before``.

    *before* and *after* hold one value per input point, in the same order; a point
    that is non-finite on either side is dropped.
    """
    before = np.asarray(before, dtype=float).ravel()
    after = np.asarray(after, dtype=float).ravel()
    keep = np.isfinite(before) & np.isfinite(after)
    before, after = before[keep], after[keep]
    n = len(before)
    diffs = after - before
    mean_diff = float(diffs.mean()) if n else None
    if n < MIN_SAMPLES:
        return _record(
            method="paired_bootstrap",
            n=n,
            n_baseline=n,
            n_candidate=n,
            mean_diff=mean_diff,
            ci=None,
            verdict=TOO_FEW_SAMPLES,
            margin_percent=margin_percent,
        )
    ci = _percentile_ci(_bootstrap_means(np.random.default_rng(SEED), diffs))
    return _record(
        method="paired_bootstrap",
        n=n,
        n_baseline=n,
        n_candidate=n,
        mean_diff=mean_diff,
        ci=ci,
        verdict=stat_verdict(*ci, float(before.mean()), direction, margin_percent),
        margin_percent=margin_percent,
    )


def unpaired_change(
    before: np.ndarray, after: np.ndarray, direction: str, margin_percent: float
) -> dict:
    """Bootstrap ``mean(after) - mean(before)``, each side resampled on its own.

    Non-finite samples are dropped; ``n`` is the smaller side's count.
    """
    before, after = _finite(before), _finite(after)
    n = min(len(before), len(after))
    mean_diff = float(after.mean() - before.mean()) if n else None
    if n < MIN_SAMPLES:
        return _record(
            method="bootstrap",
            n=n,
            n_baseline=len(before),
            n_candidate=len(after),
            mean_diff=mean_diff,
            ci=None,
            verdict=TOO_FEW_SAMPLES,
            margin_percent=margin_percent,
        )
    rng = np.random.default_rng(SEED)
    base_means = _bootstrap_means(rng, before)
    cand_means = _bootstrap_means(rng, after)
    ci = _percentile_ci(cand_means - base_means)
    return _record(
        method="bootstrap",
        n=n,
        n_baseline=len(before),
        n_candidate=len(after),
        mean_diff=mean_diff,
        ci=ci,
        verdict=stat_verdict(*ci, float(before.mean()), direction, margin_percent),
        margin_percent=margin_percent,
    )


def _points(da: xr.DataArray) -> xr.DataArray:
    """One value per input point: the mean over repeats, unit dims dropped."""
    da = da.astype(float)
    if "repeat" in da.dims:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            da = da.mean(dim="repeat", skipna=True)
    return da.squeeze(drop=True)


def not_comparable(reason: str, margin_percent: float) -> dict:
    """A record with no estimate, saying why there is none."""
    return _record(
        method=None,
        n=0,
        n_baseline=0,
        n_candidate=0,
        mean_diff=None,
        ci=None,
        verdict=NOT_COMPARABLE,
        margin_percent=margin_percent,
        reason=reason,
    )


def change_between(
    base: xr.DataArray, cand: xr.DataArray, direction: str, margin_percent: float
) -> dict:
    """The ``change`` record for one metric: paired when the sweeps match, else unpaired."""
    import xarray as xr

    base_points, cand_points = _points(base), _points(cand)
    if not base_points.dims and not cand_points.dims:
        return unpaired_change(base.values, cand.values, direction, margin_percent)
    if set(base_points.dims) != set(cand_points.dims):
        return not_comparable("the sides swept different inputs", margin_percent)
    base_points, cand_points = xr.align(base_points, cand_points, join="inner")
    if base_points.size == 0:
        return not_comparable("the sides share no swept input point", margin_percent)
    cand_points = cand_points.transpose(*base_points.dims)
    return paired_change(base_points.values, cand_points.values, direction, margin_percent)
